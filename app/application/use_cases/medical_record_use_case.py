from datetime import date, datetime
from typing import Callable
import uuid

from app.application.dtos.common import Page
from app.application.dtos.medical_record_dto import (
    AllergyCreateDTO, AllergyDTO, ConditionCreateDTO, ConditionDTO, DiagnosisCreateDTO, DiagnosisDTO,
    EmergencyContactCreateDTO, EmergencyContactDTO, MedicalRecordDTO, PatientListItemDTO, ProcedureCreateDTO,
    ProcedureDTO, ProfileDTO, ProfileUpdateDTO, TimelineEventDTO,
)
from app.application.dtos.patient_dto import PatientResponseDTO
from app.application.interfaces.appointment_repository import AppointmentFilters, AppointmentRepository
from app.application.interfaces.medical_record_repository import (
    MedicalRecordRepository, PatientDirectoryRepository, PatientSearch, TimelineQuery, TimelineRepository,
)
from app.application.interfaces.professional_repository import ProfessionalRepository
from app.application.services.clinical_links import resolve_professional
from app.application.use_cases.appointment_use_case import AppointmentUseCase
from app.domain.entities.appointment import ACTIVE_STATUSES, AppointmentStatus
from app.domain.entities.medical_record import (
    Allergy, AllergyStatus, Condition, ConditionStatus, Diagnosis, EmergencyContact, PatientProfile, Procedure,
)
from app.domain.entities.patient import Patient
from app.application.services.events import EventPublisher, NullPublisher
from app.domain.events import DomainEvent, EventType
from app.domain.exceptions.common import BusinessRuleViolation, ConflictError, EntityNotFoundError

DISCLAIMER = ("Prontuário didático com dados fictícios. As informações são educacionais "
              "e não substituem avaliação profissional.")
RECENT_DIAGNOSES = 5
UPCOMING_APPOINTMENTS = 5


def age_on(birth_date: date, today: date) -> int:
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


class MedicalRecordUseCase:
    """Prontuário eletrônico didático: leitura consolidada e registros clínicos estruturados."""

    def __init__(self, records: MedicalRecordRepository, directory: PatientDirectoryRepository,
                 timeline: TimelineRepository, appointment_repo: AppointmentRepository,
                 professional_repo: ProfessionalRepository, appointments: AppointmentUseCase,
                 clock: Callable[[], datetime] = datetime.now, events: EventPublisher = NullPublisher()):
        self.records = records
        self.events = events
        self.directory = directory
        self.timeline_repo = timeline
        self.appointment_repo = appointment_repo
        self.professional_repo = professional_repo
        self.appointments = appointments
        self.clock = clock

    # ------------------------------------------------------------- pacientes

    async def search_patients(self, search: PatientSearch) -> Page[PatientListItemDTO]:
        patients, total = await self.directory.search(search)
        today = self.clock().date()
        return Page(items=[PatientListItemDTO(
            id=p.id, full_name=p.full_name, cpf=p.cpf, birth_date=p.birth_date, age=age_on(p.birth_date, today),
            gender=p.gender, phone=p.phone, insurance_provider=p.insurance_provider,
        ) for p in patients], total=total, limit=search.limit, offset=search.offset)

    async def get_record(self, patient_id: uuid.UUID) -> MedicalRecordDTO:
        patient = await self._patient(patient_id)
        now = self.clock()
        profile = await self.records.get_profile(patient_id) or PatientProfile(patient_id=patient_id)
        allergies = [a for a in await self.records.list_allergies(patient_id) if a.status == AllergyStatus.ACTIVE]
        conditions = [c for c in await self.records.list_conditions(patient_id) if c.status != ConditionStatus.RESOLVED]
        diagnoses = (await self.records.list_diagnoses(patient_id))[:RECENT_DIAGNOSES]

        upcoming = await self.appointments.search(AppointmentFilters(
            patient_id=patient_id, statuses=list(ACTIVE_STATUSES), date_from=now, limit=UPCOMING_APPOINTMENTS))
        last = await self.appointments.search(AppointmentFilters(
            patient_id=patient_id, statuses=[AppointmentStatus.COMPLETED], newest_first=True, limit=1))

        return MedicalRecordDTO(
            patient=PatientResponseDTO(**{k: getattr(patient, k) for k in PatientResponseDTO.model_fields}),
            age=age_on(patient.birth_date, now.date()),
            profile=self._profile_dto(profile),
            active_allergies=[self._allergy_dto(a) for a in allergies],
            active_conditions=[self._condition_dto(c) for c in conditions],
            recent_diagnoses=await self._diagnosis_dtos(diagnoses),
            upcoming_appointments=upcoming.items,
            last_appointment=last.items[0] if last.items else None,
            disclaimer=DISCLAIMER,
        )

    # ------------------------------------------------------ perfil e contatos

    async def update_profile(self, patient_id: uuid.UUID, dto: ProfileUpdateDTO) -> ProfileDTO:
        profile = await self._profile(patient_id)
        profile.blood_type, profile.occupation, profile.notes = dto.blood_type, dto.occupation, dto.notes
        profile.updated_at = self.clock()
        return self._profile_dto(await self.records.save_profile(profile))

    async def add_emergency_contact(self, patient_id: uuid.UUID, dto: EmergencyContactCreateDTO) -> ProfileDTO:
        profile = await self._profile(patient_id)
        profile.add_contact(EmergencyContact(**dto.model_dump()))
        profile.updated_at = self.clock()
        return self._profile_dto(await self.records.save_profile(profile))

    async def remove_emergency_contact(self, patient_id: uuid.UUID, contact_id: uuid.UUID) -> ProfileDTO:
        profile = await self._profile(patient_id)
        profile.remove_contact(contact_id)
        profile.updated_at = self.clock()
        return self._profile_dto(await self.records.save_profile(profile))

    # ---------------------------------------------------------------- alergias

    async def list_allergies(self, patient_id: uuid.UUID) -> list[AllergyDTO]:
        await self._patient(patient_id)
        return [self._allergy_dto(a) for a in await self.records.list_allergies(patient_id)]

    async def add_allergy(self, patient_id: uuid.UUID, dto: AllergyCreateDTO) -> AllergyDTO:
        await self._patient(patient_id)
        existing = await self.records.list_allergies(patient_id)
        if any(a.status == AllergyStatus.ACTIVE and a.same_substance(dto.substance) for a in existing):
            raise ConflictError(f"Já existe uma alergia ativa a '{dto.substance}' para este paciente.")
        allergy = await self.records.save_allergy(
            Allergy(patient_id=patient_id, recorded_at=self.clock(), **dto.model_dump()))
        await self.events.publish(DomainEvent(
            event_type=EventType.ALLERGY_RECORDED, occurred_at=allergy.recorded_at, entity_type="Alergia",
            entity_id=allergy.id, patient_id=patient_id,
            summary=f"Alergia registrada: {allergy.substance} ({allergy.severity.value})."))
        return self._allergy_dto(allergy)

    async def resolve_allergy(self, patient_id: uuid.UUID, allergy_id: uuid.UUID) -> AllergyDTO:
        allergy = await self.records.get_allergy(allergy_id)
        if not allergy or allergy.patient_id != patient_id:
            raise EntityNotFoundError("Alergia", allergy_id)
        allergy.resolve(self.clock())
        return self._allergy_dto(await self.records.save_allergy(allergy))

    # --------------------------------------------------------------- condições

    async def list_conditions(self, patient_id: uuid.UUID) -> list[ConditionDTO]:
        await self._patient(patient_id)
        return [self._condition_dto(c) for c in await self.records.list_conditions(patient_id)]

    async def add_condition(self, patient_id: uuid.UUID, dto: ConditionCreateDTO) -> ConditionDTO:
        patient = await self._patient(patient_id)
        condition = Condition(patient_id=patient_id, recorded_at=self.clock(), **dto.model_dump())
        condition.validate_dates(self.clock().date())
        if condition.onset_date and condition.onset_date < patient.birth_date:
            raise BusinessRuleViolation("O início da condição não pode ser anterior ao nascimento do paciente.")
        return self._condition_dto(await self.records.save_condition(condition))

    async def change_condition_status(self, patient_id: uuid.UUID, condition_id: uuid.UUID,
                                      status: ConditionStatus) -> ConditionDTO:
        condition = await self.records.get_condition(condition_id)
        if not condition or condition.patient_id != patient_id:
            raise EntityNotFoundError("Condição", condition_id)
        condition.change_status(status, self.clock().date())
        return self._condition_dto(await self.records.save_condition(condition))

    # ------------------------------------------------------------ diagnósticos

    async def list_diagnoses(self, patient_id: uuid.UUID) -> list[DiagnosisDTO]:
        await self._patient(patient_id)
        return await self._diagnosis_dtos(await self.records.list_diagnoses(patient_id))

    async def add_diagnosis(self, patient_id: uuid.UUID, dto: DiagnosisCreateDTO) -> DiagnosisDTO:
        await self._patient(patient_id)
        data = dto.model_dump()
        data["professional_id"] = await self._resolve_professional(patient_id, dto.professional_id, dto.appointment_id)
        diagnosis = await self.records.save_diagnosis(Diagnosis(patient_id=patient_id, diagnosed_at=self.clock(), **data))
        await self.events.publish(DomainEvent(
            event_type=EventType.DIAGNOSIS_RECORDED, occurred_at=diagnosis.diagnosed_at, entity_type="Diagnostico",
            entity_id=diagnosis.id, patient_id=patient_id, professional_id=diagnosis.professional_id,
            summary=f"Diagnóstico registrado ({diagnosis.certainty.value}): {diagnosis.description}."))
        return (await self._diagnosis_dtos([diagnosis]))[0]

    async def confirm_diagnosis(self, patient_id: uuid.UUID, diagnosis_id: uuid.UUID) -> DiagnosisDTO:
        return await self._update_diagnosis(patient_id, diagnosis_id, Diagnosis.confirm)

    async def rule_out_diagnosis(self, patient_id: uuid.UUID, diagnosis_id: uuid.UUID) -> DiagnosisDTO:
        return await self._update_diagnosis(patient_id, diagnosis_id, Diagnosis.rule_out)

    # ----------------------------------------------------------- procedimentos

    async def list_procedures(self, patient_id: uuid.UUID) -> list[ProcedureDTO]:
        await self._patient(patient_id)
        return await self._procedure_dtos(await self.records.list_procedures(patient_id))

    async def add_procedure(self, patient_id: uuid.UUID, dto: ProcedureCreateDTO) -> ProcedureDTO:
        await self._patient(patient_id)
        data = dto.model_dump()
        data["performed_at"] = dto.performed_at.replace(tzinfo=None)
        data["professional_id"] = await self._resolve_professional(patient_id, dto.professional_id, dto.appointment_id)
        procedure = Procedure(patient_id=patient_id, **data)
        procedure.validate_date(self.clock())
        return (await self._procedure_dtos([await self.records.save_procedure(procedure)]))[0]

    # ---------------------------------------------------------- linha do tempo

    async def timeline(self, query: TimelineQuery, newest_first: bool = True,
                       limit: int = 50, offset: int = 0) -> Page[TimelineEventDTO]:
        await self._patient(query.patient_id)
        if query.date_from and query.date_to and query.date_from > query.date_to:
            raise BusinessRuleViolation("A data inicial deve ser anterior à data final.")
        events = sorted(await self.timeline_repo.collect(query), key=lambda e: e.occurred_at, reverse=newest_first)
        return Page(
            items=[TimelineEventDTO(occurred_at=e.occurred_at, event_type=e.event_type, title=e.title,
                                    description=e.description, status=e.status, source_id=e.source_id)
                   for e in events[offset:offset + limit]],
            total=len(events), limit=limit, offset=offset,
        )

    # ------------------------------------------------------------------ apoio

    async def _patient(self, patient_id: uuid.UUID) -> Patient:
        patient = await self.directory.get(patient_id)
        if not patient:
            raise EntityNotFoundError("Paciente", patient_id)
        return patient

    async def _profile(self, patient_id: uuid.UUID) -> PatientProfile:
        await self._patient(patient_id)
        return await self.records.get_profile(patient_id) or PatientProfile(patient_id=patient_id)

    async def _resolve_professional(self, patient_id, professional_id, appointment_id):
        return await resolve_professional(self.appointment_repo, self.professional_repo,
                                          patient_id, professional_id, appointment_id)

    async def _update_diagnosis(self, patient_id, diagnosis_id, action) -> DiagnosisDTO:
        diagnosis = await self.records.get_diagnosis(diagnosis_id)
        if not diagnosis or diagnosis.patient_id != patient_id:
            raise EntityNotFoundError("Diagnóstico", diagnosis_id)
        action(diagnosis)
        return (await self._diagnosis_dtos([await self.records.save_diagnosis(diagnosis)]))[0]

    @staticmethod
    def _profile_dto(profile: PatientProfile) -> ProfileDTO:
        return ProfileDTO(
            blood_type=profile.blood_type, occupation=profile.occupation, notes=profile.notes,
            updated_at=profile.updated_at,
            emergency_contacts=[EmergencyContactDTO(id=c.id, full_name=c.full_name, relationship=c.relationship,
                                                    phone=c.phone, is_primary=c.is_primary)
                                for c in profile.emergency_contacts],
        )

    @staticmethod
    def _allergy_dto(a: Allergy) -> AllergyDTO:
        return AllergyDTO(id=a.id, substance=a.substance, category=a.category, severity=a.severity,
                          reaction=a.reaction, status=a.status, recorded_at=a.recorded_at, resolved_at=a.resolved_at)

    @staticmethod
    def _condition_dto(c: Condition) -> ConditionDTO:
        return ConditionDTO(id=c.id, name=c.name, code=c.code, onset_date=c.onset_date, notes=c.notes,
                            status=c.status, resolved_date=c.resolved_date, recorded_at=c.recorded_at)

    async def _diagnosis_dtos(self, diagnoses: list[Diagnosis]) -> list[DiagnosisDTO]:
        names = await self.professional_repo.get_names({d.professional_id for d in diagnoses if d.professional_id})
        return [DiagnosisDTO(
            id=d.id, description=d.description, code=d.code, diagnosis_type=d.diagnosis_type, certainty=d.certainty,
            professional_id=d.professional_id, professional_name=names.get(d.professional_id),
            appointment_id=d.appointment_id, notes=d.notes, diagnosed_at=d.diagnosed_at,
        ) for d in diagnoses]

    async def _procedure_dtos(self, procedures: list[Procedure]) -> list[ProcedureDTO]:
        names = await self.professional_repo.get_names({p.professional_id for p in procedures if p.professional_id})
        return [ProcedureDTO(
            id=p.id, name=p.name, performed_at=p.performed_at, professional_id=p.professional_id,
            professional_name=names.get(p.professional_id), appointment_id=p.appointment_id, notes=p.notes,
        ) for p in procedures]
