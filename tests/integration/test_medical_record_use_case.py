from datetime import date, datetime, time, timedelta

import pytest

from app.application.dtos.appointment_dto import AppointmentCreateDTO
from app.application.dtos.medical_record_dto import (
    AllergyCreateDTO, ConditionCreateDTO, DiagnosisCreateDTO, EmergencyContactCreateDTO, EvolutionCreateDTO,
    EvolutionUpdateDTO, ProcedureCreateDTO,
    ProfileUpdateDTO,
)
from app.application.dtos.patient_dto import PatientCreateDTO
from app.application.dtos.professional_dto import ProfessionalCreateDTO, WorkingHoursDTO
from app.application.interfaces.medical_record_repository import PatientSearch, TimelineQuery
from app.application.use_cases.appointment_use_case import AppointmentUseCase
from app.application.use_cases.manage_patient_use_case import ManagePatientUseCase
from app.application.use_cases.medical_record_use_case import MedicalRecordUseCase
from app.application.use_cases.professional_use_case import ProfessionalUseCase
from app.domain.entities.medical_record import (
    AllergyCategory, AllergySeverity, BloodType, ConditionStatus, DiagnosisCertainty, EvolutionStatus,
)
from app.domain.entities.professional import ProfessionalType
from app.domain.entities.timeline import TimelineEventType as T
from app.domain.events import EventType
from app.domain.exceptions.common import BusinessRuleViolation, ConflictError, EntityNotFoundError
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.persistence.repositories.sqlalchemy_medical_record_repository import (
    SQLAlchemyMedicalRecordRepository, SQLAlchemyPatientDirectoryRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyCatalogRepository, SQLAlchemyProfessionalRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_timeline_repository import SQLAlchemyTimelineRepository

NOW = datetime(2026, 11, 9, 7, 0)  # segunda-feira


@pytest.fixture
async def ctx(db_session):
    clock = lambda: NOW  # noqa: E731
    professional_repo = SQLAlchemyProfessionalRepository(db_session)
    appointments = AppointmentUseCase(
        SQLAlchemyAppointmentRepository(db_session), professional_repo, SQLAlchemyCatalogRepository(db_session),
        SQLAlchemyPatientRepository(db_session), clock=clock)
    records = MedicalRecordUseCase(
        SQLAlchemyMedicalRecordRepository(db_session), SQLAlchemyPatientDirectoryRepository(db_session),
        SQLAlchemyTimelineRepository(db_session), SQLAlchemyAppointmentRepository(db_session),
        professional_repo, appointments, clock=clock)

    patients = ManagePatientUseCase(SQLAlchemyPatientRepository(db_session))
    maria = await patients.create_patient(PatientCreateDTO(
        full_name="Maria Silva", cpf="39053344705", birth_date=date(1990, 11, 10), gender="Feminino"))
    jose = await patients.create_patient(PatientCreateDTO(
        full_name="José Souza", cpf="52998224725", birth_date=date(1985, 5, 5), gender="Masculino",
        email="jose@example.com"))
    doctor = await ProfessionalUseCase(professional_repo, SQLAlchemyCatalogRepository(db_session)).register(
        ProfessionalCreateDTO(full_name="Dr. João (fictício)", professional_type=ProfessionalType.DOCTOR,
                              registry_number="CRM-PA 1", working_hours=[
                                  WorkingHoursDTO(weekday=0, start_time=time(8), end_time=time(12))]))
    return dict(records=records, appointments=appointments, maria=maria, jose=jose, doctor=doctor)


async def test_patient_search(ctx):
    uc = ctx["records"]
    assert (await uc.search_patients(PatientSearch(query="mar"))).items[0].full_name == "Maria Silva"
    assert (await uc.search_patients(PatientSearch(query="529.982"))).items[0].full_name == "José Souza"
    assert (await uc.search_patients(PatientSearch(query="jose@example"))).total == 1
    page = await uc.search_patients(PatientSearch(limit=1))
    assert page.total == 2 and len(page.items) == 1 and page.items[0].full_name == "José Souza"
    assert page.items[0].age == 41


async def test_record_summary_consolidates_everything(ctx):
    uc, maria = ctx["records"], ctx["maria"]
    await uc.update_profile(maria.id, ProfileUpdateDTO(blood_type=BloodType.O_NEG, occupation="Professora"))
    await uc.add_emergency_contact(maria.id, EmergencyContactCreateDTO(
        full_name="Paulo Silva", relationship="Irmão", phone="(91) 98888-7777"))
    penicillin = await uc.add_allergy(maria.id, AllergyCreateDTO(
        substance="Penicilina", category=AllergyCategory.MEDICATION, severity=AllergySeverity.SEVERE))
    dust = await uc.add_allergy(maria.id, AllergyCreateDTO(
        substance="Poeira", category=AllergyCategory.ENVIRONMENTAL, severity=AllergySeverity.MILD))
    await uc.resolve_allergy(maria.id, dust.id)
    await uc.add_condition(maria.id, ConditionCreateDTO(name="Hipertensão (fictícia)", onset_date=date(2020, 3, 1)))
    await ctx["appointments"].book(AppointmentCreateDTO(
        patient_id=maria.id, professional_id=ctx["doctor"].id, start_time=NOW.replace(hour=9)))

    record = await uc.get_record(maria.id)
    assert record.age == 35  # faz 36 apenas em 10/11
    assert record.profile.blood_type == BloodType.O_NEG
    assert record.profile.emergency_contacts[0].is_primary
    assert [a.id for a in record.active_allergies] == [penicillin.id]
    assert len(record.active_conditions) == 1
    assert len(record.upcoming_appointments) == 1 and record.last_appointment is None
    assert "não substituem avaliação profissional" in record.disclaimer


async def test_duplicate_active_allergy_is_rejected_but_resolved_one_can_return(ctx):
    uc, pid = ctx["records"], ctx["maria"].id
    dto = AllergyCreateDTO(substance="Dipirona", category=AllergyCategory.MEDICATION, severity=AllergySeverity.MODERATE)
    first = await uc.add_allergy(pid, dto)
    with pytest.raises(ConflictError):
        await uc.add_allergy(pid, dto.model_copy(update={"substance": "  dipirona "}))
    await uc.resolve_allergy(pid, first.id)
    assert (await uc.add_allergy(pid, dto)).status.value == "ATIVA"
    with pytest.raises(EntityNotFoundError):
        await uc.resolve_allergy(ctx["jose"].id, first.id)  # alergia de outro paciente


async def test_condition_rules(ctx):
    uc, maria = ctx["records"], ctx["maria"]
    with pytest.raises(BusinessRuleViolation, match="nascimento"):
        await uc.add_condition(maria.id, ConditionCreateDTO(name="Antes de nascer", onset_date=date(1980, 1, 1)))
    with pytest.raises(BusinessRuleViolation, match="futuro"):
        await uc.add_condition(maria.id, ConditionCreateDTO(name="No futuro", onset_date=date(2027, 1, 1)))
    condition = await uc.add_condition(maria.id, ConditionCreateDTO(name="Asma (fictícia)"))
    resolved = await uc.change_condition_status(maria.id, condition.id, ConditionStatus.RESOLVED)
    assert resolved.resolved_date == NOW.date()


async def test_diagnosis_linked_to_appointment(ctx):
    uc, maria, jose = ctx["records"], ctx["maria"], ctx["jose"]
    appointment = await ctx["appointments"].book(AppointmentCreateDTO(
        patient_id=maria.id, professional_id=ctx["doctor"].id, start_time=NOW.replace(hour=10)))

    diagnosis = await uc.add_diagnosis(maria.id, DiagnosisCreateDTO(
        description="Hipótese fictícia", appointment_id=appointment.id))
    assert diagnosis.professional_id == ctx["doctor"].id  # herdado da consulta
    assert diagnosis.professional_name == "Dr. João (fictício)"
    assert (await uc.confirm_diagnosis(maria.id, diagnosis.id)).certainty == DiagnosisCertainty.CONFIRMED

    with pytest.raises(BusinessRuleViolation, match="não pertence"):
        await uc.add_diagnosis(jose.id, DiagnosisCreateDTO(description="Outro paciente", appointment_id=appointment.id))

    await ctx["appointments"].cancel(appointment.id, "Motivo fictício")
    with pytest.raises(BusinessRuleViolation, match="não ocorreu"):
        await uc.add_procedure(maria.id, ProcedureCreateDTO(
            name="Curativo", performed_at=NOW - timedelta(hours=1), appointment_id=appointment.id))


async def test_timeline_merges_sources_in_order_and_filters(ctx):
    uc, maria = ctx["records"], ctx["maria"]
    await uc.add_condition(maria.id, ConditionCreateDTO(name="Rinite (fictícia)", onset_date=date(2019, 6, 1)))
    await uc.add_procedure(maria.id, ProcedureCreateDTO(name="Aferição de pressão", performed_at=NOW - timedelta(days=2)))
    await ctx["appointments"].book(AppointmentCreateDTO(
        patient_id=maria.id, professional_id=ctx["doctor"].id, start_time=NOW.replace(hour=11)))

    page = await uc.timeline(TimelineQuery(patient_id=maria.id))
    dates = [e.occurred_at for e in page.items]
    assert dates == sorted(dates, reverse=True)
    assert {e.event_type for e in page.items} >= {T.APPOINTMENT, T.PROCEDURE, T.CONDITION, T.REGISTRATION}
    assert page.items[-1].event_type == T.CONDITION  # 2019 é o evento mais antigo

    only = await uc.timeline(TimelineQuery(patient_id=maria.id, types={T.PROCEDURE}))
    assert [e.title for e in only.items] == ["Procedimento: Aferição de pressão"]
    ranged = await uc.timeline(TimelineQuery(patient_id=maria.id, date_from=datetime(2026, 1, 1)), newest_first=False)
    assert all(e.occurred_at >= datetime(2026, 1, 1) for e in ranged.items)
    assert ranged.items[0].occurred_at <= ranged.items[-1].occurred_at

    with pytest.raises(BusinessRuleViolation):
        await uc.timeline(TimelineQuery(patient_id=maria.id, date_from=datetime(2026, 2, 1), date_to=datetime(2026, 1, 1)))


class RecordingPublisher:
    def __init__(self):
        self.events = []

    async def publish(self, event):
        self.events.append(event)


async def test_evolution_draft_edit_sign_and_timeline(ctx):
    uc, maria, jose, doctor = ctx["records"], ctx["maria"], ctx["jose"], ctx["doctor"]
    uc.events = published = RecordingPublisher()

    draft = await uc.add_evolution(maria.id, EvolutionCreateDTO(
        professional_id=doctor.id, content="Paciente fictícia refere melhora da tosse."))
    assert draft.status == EvolutionStatus.DRAFT and draft.version == 1
    assert draft.professional_name == "Dr. João (fictício)" and draft.professional_type == "MEDICO"

    edited = await uc.update_evolution(maria.id, draft.id, EvolutionUpdateDTO(
        content="Paciente fictícia refere melhora da tosse; sem febre."))
    assert edited.version == 2 and edited.updated_at == NOW

    signed = await uc.sign_evolution(maria.id, draft.id)
    assert signed.status == EvolutionStatus.SIGNED and signed.signed_at == NOW
    assert [e.event_type for e in published.events] == [EventType.EVOLUTION_SIGNED]
    assert published.events[0].patient_id == maria.id and published.events[0].professional_id == doctor.id

    with pytest.raises(ConflictError):
        await uc.update_evolution(maria.id, draft.id, EvolutionUpdateDTO(content="Alteração depois de assinada."))
    with pytest.raises(EntityNotFoundError):
        await uc.sign_evolution(jose.id, draft.id)  # evolução de outro paciente
    with pytest.raises(EntityNotFoundError):
        await uc.add_evolution(maria.id, EvolutionCreateDTO(
            professional_id=maria.id, content="Profissional inexistente no cadastro."))

    assert [e.id for e in await uc.list_evolutions(maria.id)] == [draft.id]
    assert await uc.list_evolutions(jose.id) == []

    timeline = await uc.timeline(TimelineQuery(patient_id=maria.id, types={T.EVOLUTION}))
    assert len(timeline.items) == 1
    event = timeline.items[0]
    assert event.title == "Evolução clínica — Dr. João (fictício)"
    assert event.status == "ASSINADA" and event.occurred_at == NOW and "sem febre" in event.description


async def test_stale_draft_save_does_not_undo_a_signature(ctx):
    uc, maria, doctor = ctx["records"], ctx["maria"], ctx["doctor"]
    draft = await uc.add_evolution(maria.id, EvolutionCreateDTO(
        professional_id=doctor.id, content="Rascunho fictício que será assinado."))
    stale = await uc.records.get_evolution(draft.id)  # cópia lida enquanto ainda era rascunho
    await uc.sign_evolution(maria.id, draft.id)

    stale.update_content("Edição concorrente que chegou depois da assinatura.", NOW)
    with pytest.raises(ConflictError):
        await uc.records.save_evolution(stale, expected_status=EvolutionStatus.DRAFT)

    current = await uc.records.get_evolution(draft.id)
    assert current.status == EvolutionStatus.SIGNED and current.signed_at == NOW
    assert current.content == "Rascunho fictício que será assinado." and current.version == 1
