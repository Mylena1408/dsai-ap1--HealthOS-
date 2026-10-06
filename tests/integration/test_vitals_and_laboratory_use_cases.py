from datetime import date, datetime, timedelta

import pytest

from app.application.dtos.clinical_monitoring_dto import ExamRequestCreateDTO, VitalSignsCreateDTO
from app.application.dtos.patient_dto import PatientCreateDTO
from app.application.dtos.professional_dto import ProfessionalCreateDTO, ProfessionalUpdateDTO
from app.application.interfaces.clinical_monitoring_repository import ExamRequestFilters
from app.application.use_cases.laboratory_use_case import LaboratoryUseCase
from app.application.use_cases.manage_patient_use_case import ManagePatientUseCase
from app.application.use_cases.professional_use_case import ProfessionalUseCase
from app.application.use_cases.vital_signs_use_case import VitalSignsUseCase, trend
from app.domain.entities.laboratory import ExamPriority, ExamStatus as S
from app.domain.entities.professional import ProfessionalStatus, ProfessionalType
from app.domain.entities.reference_range import ResultFlag as F
from app.domain.entities.vital_signs import BmiCategory, VitalMetric as M
from app.domain.exceptions.common import BusinessRuleViolation, EntityNotFoundError, InvalidTransitionError
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.persistence.repositories.sqlalchemy_clinical_monitoring_repository import (
    SQLAlchemyLaboratoryRepository, SQLAlchemyVitalSignsRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_medical_record_repository import (
    SQLAlchemyPatientDirectoryRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyCatalogRepository, SQLAlchemyProfessionalRepository,
)
from app.infrastructure.seed.lab_catalog import ensure_lab_catalog


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
async def ctx(db_session):
    clock = Clock(datetime(2026, 10, 6, 8, 0))
    directory = SQLAlchemyPatientDirectoryRepository(db_session)
    professional_repo = SQLAlchemyProfessionalRepository(db_session)
    lab_repo = SQLAlchemyLaboratoryRepository(db_session)
    assert await ensure_lab_catalog(db_session) == 13  # 11 exames + 2 laboratórios
    assert await ensure_lab_catalog(db_session) == 0   # idempotente

    patient = await ManagePatientUseCase(SQLAlchemyPatientRepository(db_session)).create_patient(PatientCreateDTO(
        full_name="Paciente Laboratório", cpf="39053344705", birth_date=date(1980, 1, 1), gender="Outro"))
    professionals = ProfessionalUseCase(professional_repo, SQLAlchemyCatalogRepository(db_session))
    doctor = await professionals.register(ProfessionalCreateDTO(
        full_name="Dra. Validadora (fictícia)", professional_type=ProfessionalType.DOCTOR, registry_number="CRM-T 1"))
    return dict(
        clock=clock, patient=patient, doctor=doctor, professionals=professionals, lab_repo=lab_repo,
        vitals=VitalSignsUseCase(SQLAlchemyVitalSignsRepository(db_session), directory, professional_repo, clock=clock),
        lab=LaboratoryUseCase(lab_repo, directory, professional_repo, SQLAlchemyAppointmentRepository(db_session),
                              clock=clock),
    )


# ------------------------------------------------------------------ sinais vitais

async def test_vital_signs_bmi_uses_last_known_height_and_summary_trends(ctx):
    uc, pid, clock = ctx["vitals"], ctx["patient"].id, ctx["clock"]
    await uc.record(pid, VitalSignsCreateDTO(recorded_at=clock.now - timedelta(days=30), height_cm=170, weight_kg=70,
                                             systolic=118, diastolic=76))
    latest = await uc.record(pid, VitalSignsCreateDTO(weight_kg=82, systolic=145, diastolic=92, heart_rate=70))
    assert latest.bmi == 28.4 and latest.bmi_category == BmiCategory.OVERWEIGHT
    assert latest.flags[M.SYSTOLIC] == F.HIGH

    page = await uc.page(pid, None, None, limit=10, offset=0)
    assert page.total == 2 and page.items[0].id == latest.id  # mais recente primeiro
    assert page.items[1].bmi == 24.2

    summary = await uc.summary(pid)
    by_metric = {m.metric: m for m in summary.metrics}
    assert by_metric[M.WEIGHT].trend == "SUBINDO" and by_metric[M.WEIGHT].previous == 70
    assert by_metric[M.WEIGHT].flag is None  # peso não tem faixa
    assert by_metric[M.SYSTOLIC].flag == F.HIGH and len(by_metric[M.SYSTOLIC].series) == 2
    assert by_metric[M.HEART_RATE].trend is None  # só uma medida
    assert [p[1] for p in by_metric[M.BMI].series] == [24.2, 28.4]


async def test_vital_signs_validation(ctx):
    uc, pid, clock = ctx["vitals"], ctx["patient"].id, ctx["clock"]
    with pytest.raises(BusinessRuleViolation, match="futuro"):
        await uc.record(pid, VitalSignsCreateDTO(recorded_at=clock.now + timedelta(hours=1), heart_rate=80))
    with pytest.raises(EntityNotFoundError):
        await uc.record(ctx["doctor"].id, VitalSignsCreateDTO(heart_rate=80))


def test_trend_tolerance():
    assert trend(None, 10) is None
    assert trend(100, 101) == "ESTAVEL"
    assert trend(100, 110) == "SUBINDO"
    assert trend(100, 90) == "DESCENDO"


# -------------------------------------------------------------------- laboratório

async def exam_type_id(ctx, code):
    return (await ctx["lab_repo"].get_exam_type_by_code(code)).id


async def test_complete_laboratory_flow(ctx):
    lab, clock = ctx["lab"], ctx["clock"]
    labs = await lab.laboratories()
    exam = await lab.request(ExamRequestCreateDTO(
        patient_id=ctx["patient"].id, exam_type_id=await exam_type_id(ctx, "LIPID"), requested_by=ctx["doctor"].id,
        laboratory_id=labs[0].id, priority=ExamPriority.URGENT, clinical_indication="Rastreamento fictício"))
    assert exam.status == S.REQUESTED and exam.exam_name == "Perfil lipídico (colesterol)"
    assert exam.requested_by_name == "Dra. Validadora (fictícia)"
    assert exam.allowed_transitions == [S.SCHEDULED, S.COLLECTED, S.CANCELLED]

    await lab.schedule(exam.id, clock.now + timedelta(hours=2))
    clock.now += timedelta(hours=2)
    collected = await lab.collect(exam.id)
    assert collected.sample_code and collected.expected_by == collected.collected_at + timedelta(hours=24)
    await lab.start_processing(exam.id)

    with pytest.raises(BusinessRuleViolation, match="Faltam"):
        await lab.record_results(exam.id, {"CT": 200})
    resulted = await lab.record_results(exam.id, {"CT": 240, "HDL": 35, "LDL": 160}, "Amostra sem hemólise")
    assert [r.flag for r in resulted.results] == [F.HIGH, F.LOW, F.HIGH] and resulted.has_abnormal_results

    returned = await lab.return_for_correction(exam.id, "Conferir LDL")
    assert returned.status == S.PROCESSING and returned.results == []
    await lab.record_results(exam.id, {"CT": 240, "HDL": 35, "LDL": 150})

    with pytest.raises(InvalidTransitionError):
        await lab.release(exam.id)  # precisa validar antes
    validated = await lab.validate(exam.id, ctx["doctor"].id)
    assert validated.validated_by_name == "Dra. Validadora (fictícia)"
    released = await lab.release(exam.id)
    assert released.status == S.RELEASED
    assert [h.to_status for h in released.history] == [
        S.REQUESTED, S.SCHEDULED, S.COLLECTED, S.PROCESSING, S.RESULTED, S.PROCESSING, S.RESULTED, S.VALIDATED,
        S.RELEASED]

    history = await lab.analyte_history(ctx["patient"].id, "ldl")
    assert history.points[0][1:] == (150.0, F.HIGH) and history.unit == "mg/dL"


async def test_validator_must_be_active_and_analyte_history_ignores_unreleased(ctx):
    lab = ctx["lab"]
    exam = await lab.request(ExamRequestCreateDTO(patient_id=ctx["patient"].id,
                                                  exam_type_id=await exam_type_id(ctx, "GLI")))
    await lab.collect(exam.id)
    await lab.start_processing(exam.id)
    await lab.record_results(exam.id, {"GLI": 45})
    assert (await lab.get(exam.id)).has_critical_results

    await ctx["professionals"].update(ctx["doctor"].id, ProfessionalUpdateDTO(status=ProfessionalStatus.ON_LEAVE))
    with pytest.raises(BusinessRuleViolation, match="ativos"):
        await lab.validate(exam.id, ctx["doctor"].id)
    assert (await lab.analyte_history(ctx["patient"].id, "GLI")).points == []


async def test_search_filters(ctx):
    lab, pid = ctx["lab"], ctx["patient"].id
    normal = await lab.request(ExamRequestCreateDTO(patient_id=pid, exam_type_id=await exam_type_id(ctx, "K")))
    abnormal = await lab.request(ExamRequestCreateDTO(patient_id=pid, exam_type_id=await exam_type_id(ctx, "K"),
                                                      priority=ExamPriority.URGENT))
    for exam, value in ((normal, 4.2), (abnormal, 6.0)):
        await lab.collect(exam.id)
        await lab.start_processing(exam.id)
        await lab.record_results(exam.id, {"K": value})
    cancelled = await lab.request(ExamRequestCreateDTO(patient_id=pid, exam_type_id=await exam_type_id(ctx, "TSH")))
    await lab.cancel(cancelled.id, "Pedido duplicado")

    assert [e.id for e in (await lab.search(ExamRequestFilters(only_abnormal=True))).items] == [abnormal.id]
    assert (await lab.search(ExamRequestFilters(statuses=[S.CANCELLED]))).total == 1
    assert (await lab.search(ExamRequestFilters(priority=ExamPriority.URGENT))).items[0].id == abnormal.id
    page = await lab.search(ExamRequestFilters(patient_id=pid, limit=2))
    assert page.total == 3 and len(page.items) == 2 and page.items[0].patient_name == "Paciente Laboratório"
