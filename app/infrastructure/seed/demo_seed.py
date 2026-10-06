"""Popula o banco com dados fictícios de demonstração.

Idempotente: os dados são gerados a partir de uma semente fixa, então uma nova
execução encontra os mesmos CPFs/nomes já cadastrados e não duplica registros.
Os casos de uso são reutilizados para que as regras de domínio continuem valendo.
"""
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.patient_dto import PatientCreateDTO
from app.application.use_cases.manage_patient_use_case import ManagePatientUseCase
from app.application.use_cases.pharmacy_use_case import PharmacyUseCase
from app.infrastructure.persistence.models.medication_model import MedicationModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.repositories.sqlalchemy_medication_repository import (
    SQLAlchemyInventoryRepository,
    SQLAlchemyMedicationRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.seed.fake_data import MEDICATIONS, STOCK_LOCATIONS, fake_patient
from app.infrastructure.seed.scheduling_seed import seed_appointments, seed_catalog_and_professionals

DEFAULT_SEED = 2026


@dataclass
class SeedReport:
    created: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)

    def add(self, entity: str, created: bool) -> None:
        bucket = self.created if created else self.skipped
        bucket[entity] = bucket.get(entity, 0) + 1


async def seed_patients(session: AsyncSession, total: int, rng: random.Random, report: SeedReport) -> None:
    use_case = ManagePatientUseCase(SQLAlchemyPatientRepository(session))
    existing = set((await session.execute(select(PatientModel.cpf))).scalars().all())
    for _ in range(total):
        data = fake_patient(rng)
        if data["cpf"] in existing:
            report.add("patients", created=False)
            continue
        await use_case.create_patient(PatientCreateDTO(**data))
        existing.add(data["cpf"])
        report.add("patients", created=True)


async def seed_medications(session: AsyncSession, rng: random.Random, report: SeedReport) -> None:
    pharmacy = PharmacyUseCase(SQLAlchemyMedicationRepository(session), SQLAlchemyInventoryRepository(session))
    existing = set((await session.execute(select(MedicationModel.name))).scalars().all())
    for name, generic, dosage, unit in MEDICATIONS:
        if name in existing:
            report.add("medications", created=False)
            continue
        medication = await pharmacy.register_medication(
            name=name, generic_name=generic, dosage=dosage, unit=unit,
            manufacturer="Laboratório Fictício", description="Item de demonstração.",
        )
        report.add("medications", created=True)
        # Estoque só é criado junto com o medicamento, para não crescer a cada execução.
        for location in STOCK_LOCATIONS:
            # Algumas quantidades ficam abaixo do mínimo (10) para demonstrar estoque crítico.
            quantity = rng.choice([0, 4, 8, 25, 60, 120, 300])
            expiration = datetime.now() + timedelta(days=rng.randint(15, 720))
            await pharmacy.add_inventory_stock(medication.id, location, quantity, expiration)
            report.add("inventory_items", created=True)


async def seed_demo_data(session: AsyncSession, patients: int = 50, appointments: int = 100,
                         seed: int = DEFAULT_SEED, now: datetime | None = None) -> SeedReport:
    rng = random.Random(seed)
    report = SeedReport()
    await seed_patients(session, patients, rng, report)
    await seed_medications(session, rng, report)
    await seed_catalog_and_professionals(session, rng, report)
    await seed_appointments(session, appointments, rng, report, now or datetime.now().replace(second=0, microsecond=0))
    await session.commit()
    return report
