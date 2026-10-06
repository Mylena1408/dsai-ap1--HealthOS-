from datetime import datetime

from sqlalchemy import func, select

from app.application.interfaces.appointment_repository import AppointmentFilters
from app.application.interfaces.clinical_monitoring_repository import ExamRequestFilters
from app.domain.entities.laboratory import ExamStatus
from app.infrastructure.persistence.repositories.sqlalchemy_clinical_monitoring_repository import (
    SQLAlchemyLaboratoryRepository,
)
from app.domain.entities.appointment import AppointmentStatus as S
from app.infrastructure.persistence.models.appointment_model import AppointmentModel
from app.infrastructure.persistence.models.medical_record_model import (
    ConditionModel, DiagnosisModel, PatientProfileModel,
)
from app.infrastructure.persistence.models.professional_model import ProfessionalModel
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository

from app.application.use_cases.pharmacy_use_case import PharmacyUseCase
from app.infrastructure.persistence.models.medication_model import InventoryItemModel, MedicationModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.repositories.sqlalchemy_medication_repository import (
    SQLAlchemyInventoryRepository,
    SQLAlchemyMedicationRepository,
)
from app.infrastructure.seed.demo_seed import seed_demo_data
from app.infrastructure.seed.fake_data import MEDICATIONS, PROFESSIONAL_MIX, STOCK_LOCATIONS


async def _count(session, model):
    return await session.scalar(select(func.count()).select_from(model))


async def test_seed_creates_fictitious_data_and_is_idempotent(db_session):
    report = await seed_demo_data(db_session, patients=20)
    assert report.created["patients"] == 20
    assert report.created["medications"] == len(MEDICATIONS)
    assert await _count(db_session, InventoryItemModel) == len(MEDICATIONS) * len(STOCK_LOCATIONS)

    again = await seed_demo_data(db_session, patients=20)
    assert again.created == {}
    assert again.skipped["patients"] == 20
    assert await _count(db_session, PatientModel) == 20
    assert await _count(db_session, MedicationModel) == len(MEDICATIONS)


async def test_seed_produces_critical_stock_for_demonstration(db_session):
    await seed_demo_data(db_session, patients=1)
    pharmacy = PharmacyUseCase(SQLAlchemyMedicationRepository(db_session), SQLAlchemyInventoryRepository(db_session))
    assert await pharmacy.get_critical_stock_report()


async def test_seed_professionals_and_coherent_appointments(db_session):
    now = datetime(2026, 10, 6, 12, 0)
    report = await seed_demo_data(db_session, patients=30, appointments=100, now=now)
    assert report.created["professionals"] == sum(amount for *_, amount in PROFESSIONAL_MIX) == 20
    assert report.created["appointments"] == 100
    assert await _count(db_session, ProfessionalModel) == 20

    appointments, total = await SQLAlchemyAppointmentRepository(db_session).search(AppointmentFilters(limit=1000))
    assert total == 100
    for a in appointments:
        # Histórico começa no agendamento, é cronológico e termina no status atual.
        assert a.history[0].from_status is None
        assert [h.changed_at for h in a.history] == sorted(h.changed_at for h in a.history)
        assert a.history[-1].to_status == a.status
        if a.start_time > now:
            assert a.status in (S.SCHEDULED, S.CONFIRMED, S.CANCELLED)
        else:
            assert a.status in (S.COMPLETED, S.NO_SHOW, S.CANCELLED)

    active = [a for a in appointments if a.is_active]
    for owner in ("professional_id", "patient_id"):
        for i, a in enumerate(active):
            for b in active[i + 1:]:
                if getattr(a, owner) == getattr(b, owner):
                    assert not a.overlaps(b.start_time, b.end_time)

    again = await seed_demo_data(db_session, patients=30, appointments=100, now=now)
    assert "appointments" not in again.created and "professionals" not in again.created


async def test_seed_medical_records_are_coherent_and_idempotent(db_session):
    now = datetime(2026, 10, 6, 12, 0)
    report = await seed_demo_data(db_session, patients=25, appointments=60, now=now)
    assert report.created["medical_records"] == 25
    assert await _count(db_session, PatientProfileModel) == 25

    patients = {p.id: p for p in (await db_session.scalars(select(PatientModel))).all()}
    for condition in (await db_session.scalars(select(ConditionModel))).all():
        assert patients[condition.patient_id].birth_date < condition.onset_date <= now.date()
        if condition.resolved_date:
            assert condition.onset_date <= condition.resolved_date <= now.date()

    finished = {a.id: a for a in (await db_session.scalars(
        select(AppointmentModel).where(AppointmentModel.status == "FINALIZADA"))).all()}
    for diagnosis in (await db_session.scalars(select(DiagnosisModel))).all():
        appointment = finished[diagnosis.appointment_id]  # só consultas finalizadas
        assert appointment.patient_id == diagnosis.patient_id
        assert diagnosis.diagnosed_at == appointment.end_time

    again = await seed_demo_data(db_session, patients=25, appointments=60, now=now)
    assert "medical_records" not in again.created
    assert again.skipped["medical_records"] == 25


async def test_seed_vitals_and_exams_are_coherent(db_session):
    now = datetime(2026, 10, 6, 12, 0)
    report = await seed_demo_data(db_session, patients=15, appointments=20, exams=120, now=now)
    assert report.created["exam_requests"] == 120 and report.created["vital_signs"] >= 15 * 3

    repo = SQLAlchemyLaboratoryRepository(db_session)
    exams, total = await repo.search_requests(ExamRequestFilters(limit=500))
    assert total == 120
    assert len({e.status for e in exams}) >= 6  # a fila do laboratório tem exames em várias etapas
    for exam in exams:
        moments = [h.changed_at for h in exam.history]
        assert moments == sorted(moments) and moments[-1] <= now, exam.status
        assert exam.history[-1].to_status == exam.status
        if exam.status in (ExamStatus.RELEASED, ExamStatus.VALIDATED, ExamStatus.RESULTED):
            assert exam.results
        if exam.status == ExamStatus.RELEASED:
            assert exam.validated_by and exam.released_at >= exam.validated_at >= exam.collected_at
        if exam.status == ExamStatus.SCHEDULED:
            assert exam.scheduled_for > exam.history[-1].changed_at

    again = await seed_demo_data(db_session, patients=15, appointments=20, exams=120, now=now)
    assert "exam_requests" not in again.created and "vital_signs" not in again.created
