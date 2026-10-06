"""Dados fictícios da farmácia: categorias, lotes, prescrições e dispensações.

Os lotes detalham o estoque legado já existente (mesmo total por medicamento/local).
Prescrições e dispensações passam pelo PrescriptionUseCase com um relógio
controlado, então as regras (papéis, alergias, validade, FEFO) valem também aqui.
"""
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.pharmacy_dto import (
    DispensationCreateDTO, DispensationItemDTO, PrescriptionCreateDTO, PrescriptionItemCreateDTO,
)
from app.application.interfaces.professional_repository import ProfessionalFilters
from app.application.services.stock_service import StockService
from app.application.use_cases.prescription_use_case import PrescriptionUseCase, allergy_matches
from app.domain.entities.appointment import AppointmentStatus
from app.domain.entities.medical_record import AllergyStatus
from app.domain.entities.pharmacy import (
    InventoryMovement, MedicationCategory, MedicationDetails, MovementType, StockLot,
)
from app.domain.entities.professional import ProfessionalType
from app.domain.exceptions.base import DomainException
from app.infrastructure.persistence.models.appointment_model import AppointmentModel
from app.infrastructure.persistence.models.medication_model import InventoryItemModel, MedicationModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.models.pharmacy_model import PrescriptionModel, StockLotModel
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.persistence.repositories.sqlalchemy_medical_record_repository import (
    SQLAlchemyMedicalRecordRepository, SQLAlchemyPatientDirectoryRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_medication_repository import SQLAlchemyInventoryRepository
from app.infrastructure.persistence.repositories.sqlalchemy_pharmacy_repository import SQLAlchemyPharmacyRepository
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyProfessionalRepository,
)

if TYPE_CHECKING:
    from app.infrastructure.seed.demo_seed import SeedReport

CATEGORY_BY_GENERIC = {
    "Paracetamol": "Analgésicos e antitérmicos", "Dipirona sódica": "Analgésicos e antitérmicos",
    "Ibuprofeno": "Anti-inflamatórios", "Amoxicilina": "Antibióticos", "Omeprazol": "Gastroprotetores",
    "Losartana potássica": "Anti-hipertensivos", "Metformina": "Antidiabéticos", "Sinvastatina": "Hipolipemiantes",
    "Cloreto de sódio 0,9%": "Soluções e hidratação", "Dexametasona": "Corticoides",
    "Insulina humana NPH": "Antidiabéticos", "Salbutamol": "Broncodilatadores",
}
DISPENSING_LOCATION = "FARMACIA_CENTRAL"
PRESCRIPTION_WINDOW_DAYS = 90
# Dimensionado para a demanda de ~150 prescrições: a maioria é dispensada e alguns itens esgotam.
REPLENISHMENT_QUANTITY = 1000
POSOLOGY = [("1 comprimido", "de 8 em 8 horas", 7), ("1 comprimido", "de 12 em 12 horas", 10),
            ("1 comprimido", "1 vez ao dia", 30), ("2 jatos", "se falta de ar", 30), ("10 UI", "antes do café", 30)]


class _Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


async def seed_pharmacy(session: AsyncSession, rng: random.Random, report: "SeedReport", now: datetime,
                        prescriptions: int = 150) -> None:
    repo = SQLAlchemyPharmacyRepository(session)
    await _seed_catalog(session, repo, report)
    await _seed_lots(session, repo, rng, report, now)
    await _seed_prescriptions(session, repo, rng, report, now, prescriptions)


async def _seed_catalog(session, repo, report) -> None:
    categories = {}
    for name in sorted(set(CATEGORY_BY_GENERIC.values())):
        existing = await repo.get_category_by_name(name)
        categories[name] = existing or await repo.save_category(MedicationCategory(name=name))
        report.add("medication_categories", created=existing is None)
    for medication in (await session.scalars(select(MedicationModel))).all():
        category = categories.get(CATEGORY_BY_GENERIC.get(medication.generic_name))
        if category and not await repo.get_details(medication.id):
            await repo.save_details(MedicationDetails(medication_id=medication.id, category_id=category.id))


async def _seed_lots(session, repo, rng, report, now) -> None:
    """Divide o total legado de cada medicamento/local em 1 a 3 lotes com validades distintas."""
    if await session.scalar(select(func.count()).select_from(StockLotModel)):
        report.add("stock_lots", created=False)
        return
    items = (await session.scalars(select(InventoryItemModel).where(InventoryItemModel.quantity > 0)
                                   .order_by(InventoryItemModel.medication_id, InventoryItemModel.location_id))).all()
    for item in items:
        remaining, parts = item.quantity, rng.randint(1, 3)
        for index in range(parts):
            quantity = remaining if index == parts - 1 else round(remaining * rng.uniform(0.3, 0.6))
            if quantity <= 0:
                continue
            remaining -= quantity
            # Alguns lotes vencem em breve (ou já venceram) para demonstrar alertas e descarte.
            days = rng.choice([-5, 12, 25, 60, 120, 240, 400])
            received = now - timedelta(days=rng.randint(20, 200))
            lot = await repo.save_lot(StockLot(
                medication_id=item.medication_id, location=item.location_id,
                lot_number=f"L{rng.randint(1000, 9999)}-{index + 1}",
                expiration_date=(now + timedelta(days=days)).date(), quantity=quantity, received_at=received))
            await repo.add_movement(InventoryMovement(
                medication_id=item.medication_id, location=item.location_id, movement_type=MovementType.RECEIPT,
                quantity=quantity, occurred_at=received, balance_after=item.quantity, lot_id=lot.id,
                reason=f"Recebimento do lote {lot.lot_number} (carga inicial fictícia)"))
            report.add("stock_lots", created=True)


async def _seed_prescriptions(session, repo, rng, report, now, total) -> None:
    if await session.scalar(select(func.count()).select_from(PrescriptionModel)):
        report.add("prescriptions", created=False)
        return
    clock = _Clock(now)
    stock = StockService(repo, SQLAlchemyInventoryRepository(session))
    professional_repo = SQLAlchemyProfessionalRepository(session)
    records = SQLAlchemyMedicalRecordRepository(session)
    use_case = PrescriptionUseCase(
        repo, SQLAlchemyPatientDirectoryRepository(session), professional_repo,
        SQLAlchemyAppointmentRepository(session), records,
        stock, clock=clock)

    professionals, _ = await professional_repo.search(ProfessionalFilters(limit=1000))
    doctors = [p.id for p in professionals if p.professional_type == ProfessionalType.DOCTOR]
    pharmacists = [p.id for p in professionals if p.professional_type == ProfessionalType.PHARMACIST]
    medications = (await session.scalars(select(MedicationModel).order_by(MedicationModel.name))).all()
    patient_ids = list((await session.scalars(select(PatientModel.id).order_by(PatientModel.cpf))).all())
    if not (doctors and pharmacists and medications and patient_ids):
        return
    domain_medications = await repo.medications_by_ids({m.id for m in medications})

    # Reposição inicial na farmácia central para quase todo o catálogo (dois itens seguem
    # com estoque baixo, para a demonstração de estoque crítico).
    for medication in rng.sample(medications, k=max(1, len(medications) - 2)):
        await stock.receive(medication.id, DISPENSING_LOCATION, f"REP-{rng.randint(1000, 9999)}",
                            (now + timedelta(days=rng.randint(300, 700))).date(), REPLENISHMENT_QUANTITY,
                            now - timedelta(days=PRESCRIPTION_WINDOW_DAYS + 5))
        report.add("stock_lots", created=True)

    # Eventos de prescrição: consultas finalizadas com médicos + renovações avulsas, em ordem cronológica.
    appointments = (await session.scalars(
        select(AppointmentModel).where(AppointmentModel.status == AppointmentStatus.COMPLETED.value,
                                       AppointmentModel.professional_id.in_(doctors)))).all()
    events = [(a.end_time, a.patient_id, a.professional_id, a.id) for a in appointments if rng.random() < 0.8]
    while len(events) < total:
        issued = now - timedelta(days=rng.randint(0, PRESCRIPTION_WINDOW_DAYS), hours=rng.randint(1, 10))
        events.append((issued.replace(second=0, microsecond=0), rng.choice(patient_ids), rng.choice(doctors), None))
    events.sort(key=lambda event: event[0])

    for issued_at, patient_id, doctor_id, appointment_id in events:
        allergies = [a for a in await records.list_allergies(patient_id) if a.status == AllergyStatus.ACTIVE]
        safe = [m for m in medications
                if not any(allergy_matches(a.substance, domain_medications[m.id]) for a in allergies)]
        items = []
        for medication in rng.sample(safe, k=min(len(safe), rng.choice([1, 1, 2, 3]))):
            dose, frequency, days = rng.choice(POSOLOGY)
            quantity = min(days, 60) if medication.is_controlled_substance else days * rng.choice([1, 1, 2])
            items.append(PrescriptionItemCreateDTO(medication_id=medication.id, dose=dose, frequency=frequency,
                                                   duration_days=days, quantity=quantity))
        clock.now = issued_at
        prescription = await use_case.prescribe(PrescriptionCreateDTO(
            patient_id=patient_id, prescriber_id=doctor_id, appointment_id=appointment_id, items=items))
        report.add("prescriptions", created=True)

        # A maioria é dispensada algumas horas depois, se houver estoque válido no momento.
        dispense_at = issued_at + timedelta(hours=rng.randint(1, 30))
        if rng.random() < 0.8 and dispense_at < now:
            clock.now = dispense_at
            pharmacist = rng.choice(pharmacists)
            try:
                # Savepoint: se faltar estoque para um item, a baixa dos anteriores é desfeita.
                async with session.begin_nested():
                    await use_case.dispense(DispensationCreateDTO(
                        prescription_id=prescription.id, pharmacist_id=pharmacist, location=DISPENSING_LOCATION,
                        items=[DispensationItemDTO(prescription_item_id=i.id, quantity=i.quantity)
                               for i in prescription.items]))
                report.add("dispensations", created=True)
            except DomainException:
                report.add("dispensations_without_stock", created=True)
        clock.now = now
