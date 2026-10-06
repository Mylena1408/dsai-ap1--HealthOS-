from sqlalchemy import func, select

from app.application.use_cases.pharmacy_use_case import PharmacyUseCase
from app.infrastructure.persistence.models.medication_model import InventoryItemModel, MedicationModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.repositories.sqlalchemy_medication_repository import (
    SQLAlchemyInventoryRepository,
    SQLAlchemyMedicationRepository,
)
from app.infrastructure.seed.demo_seed import seed_demo_data
from app.infrastructure.seed.fake_data import MEDICATIONS, STOCK_LOCATIONS


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
