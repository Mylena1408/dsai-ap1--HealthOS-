from datetime import datetime

from sqlalchemy import func, select

from app.application.interfaces.appointment_repository import AppointmentFilters
from app.domain.entities.appointment import AppointmentStatus as S
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
