from datetime import date, datetime, timedelta

import pytest

from app.application.dtos.medical_record_dto import AllergyCreateDTO
from app.application.dtos.patient_dto import PatientCreateDTO
from app.application.dtos.pharmacy_dto import (
    DispensationCreateDTO, DispensationItemDTO, LotReceiveDTO, MedicationDetailsDTO, PrescriptionCreateDTO,
    PrescriptionItemCreateDTO,
)
from app.application.dtos.professional_dto import ProfessionalCreateDTO
from app.application.interfaces.pharmacy_repository import LotFilters, MovementFilters
from app.application.services.stock_service import StockService
from app.application.use_cases.manage_patient_use_case import ManagePatientUseCase
from app.application.use_cases.pharmacy_stock_use_case import PharmacyStockUseCase
from app.application.use_cases.pharmacy_use_case import PharmacyUseCase
from app.application.use_cases.prescription_use_case import PrescriptionUseCase, allergy_matches
from app.application.use_cases.professional_use_case import ProfessionalUseCase
from app.domain.entities.medical_record import AllergyCategory, AllergySeverity
from app.domain.entities.pharmacy import CatalogStatus, ItemStatus, MovementType, PrescriptionStatus as PS
from app.domain.entities.professional import ProfessionalType
from app.domain.exceptions.common import BusinessRuleViolation, ConflictError
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.persistence.repositories.sqlalchemy_medical_record_repository import (
    SQLAlchemyMedicalRecordRepository, SQLAlchemyPatientDirectoryRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_medication_repository import (
    SQLAlchemyInventoryRepository, SQLAlchemyMedicationRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.persistence.repositories.sqlalchemy_pharmacy_repository import SQLAlchemyPharmacyRepository
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyCatalogRepository, SQLAlchemyProfessionalRepository,
)
from app.application.use_cases.medical_record_use_case import MedicalRecordUseCase

TODAY = date.today()
LOCATION = "FARMACIA_CENTRAL"


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
async def ctx(db_session):
    clock = Clock(datetime.now().replace(microsecond=0))
    repo = SQLAlchemyPharmacyRepository(db_session)
    inventory = SQLAlchemyInventoryRepository(db_session)
    stock_service = StockService(repo, inventory)
    legacy = PharmacyUseCase(SQLAlchemyMedicationRepository(db_session), inventory)
    professional_repo = SQLAlchemyProfessionalRepository(db_session)
    professionals = ProfessionalUseCase(professional_repo, SQLAlchemyCatalogRepository(db_session))
    records_repo = SQLAlchemyMedicalRecordRepository(db_session)
    directory = SQLAlchemyPatientDirectoryRepository(db_session)

    amoxicillin = await legacy.register_medication("Amoxicilina Demo", "Amoxicilina", "500mg", "COMPRIMIDO")
    clonazepam = await legacy.register_medication("Clonazepam Demo", "Clonazepam", "2mg", "COMPRIMIDO", is_controlled=True)
    patient = await ManagePatientUseCase(SQLAlchemyPatientRepository(db_session)).create_patient(PatientCreateDTO(
        full_name="Paciente Farmácia", cpf="39053344705", birth_date=date(1980, 1, 1), gender="Outro"))
    doctor = await professionals.register(ProfessionalCreateDTO(
        full_name="Dr. Prescritor", professional_type=ProfessionalType.DOCTOR, registry_number="CRM-F 1"))
    nurse = await professionals.register(ProfessionalCreateDTO(
        full_name="Enf. Sem Prescrição", professional_type=ProfessionalType.NURSE, registry_number="COREN-F 1"))
    pharmacist = await professionals.register(ProfessionalCreateDTO(
        full_name="Farm. Dispensadora", professional_type=ProfessionalType.PHARMACIST, registry_number="CRF-F 1"))

    return dict(
        clock=clock, repo=repo, inventory=inventory, legacy=legacy, patient=patient, doctor=doctor, nurse=nurse,
        pharmacist=pharmacist, amoxicillin=amoxicillin, clonazepam=clonazepam,
        stock=PharmacyStockUseCase(repo, stock_service, SQLAlchemyMedicationRepository(db_session), clock=clock),
        rx=PrescriptionUseCase(repo, directory, professional_repo, SQLAlchemyAppointmentRepository(db_session),
                               records_repo, stock_service, clock=clock),
        records=MedicalRecordUseCase(records_repo, directory, None, None, professional_repo, None, clock=clock),
    )


async def receive(ctx, medication, lot_number, days, quantity):
    return await ctx["stock"].receive_lot(LotReceiveDTO(
        medication_id=medication.id, location=LOCATION, lot_number=lot_number,
        expiration_date=TODAY + timedelta(days=days), quantity=quantity))


def rx_item(medication, quantity=20):
    return PrescriptionItemCreateDTO(medication_id=medication.id, dose="1 comprimido", frequency="8/8h",
                                     duration_days=7, quantity=quantity)


async def test_receive_lots_updates_legacy_total_and_records_movements(ctx):
    await receive(ctx, ctx["amoxicillin"], "a1", 200, 30)
    await receive(ctx, ctx["amoxicillin"], "a2", 40, 20)
    aggregate = await ctx["inventory"].get_by_medication_and_location(ctx["amoxicillin"].id, LOCATION)
    assert aggregate.quantity == 50
    assert aggregate.expiration_date.date() == TODAY + timedelta(days=40)  # validade mais próxima

    with pytest.raises(ConflictError):
        await receive(ctx, ctx["amoxicillin"], "A1", 300, 5)  # mesmo lote (normalizado)
    with pytest.raises(BusinessRuleViolation, match="vencido"):
        await receive(ctx, ctx["amoxicillin"], "old", -1, 5)

    movements = await ctx["stock"].search_movements(MovementFilters(medication_id=ctx["amoxicillin"].id))
    assert [m.movement_type for m in movements.items] == [MovementType.RECEIPT] * 2
    overview = {o.name: o for o in await ctx["stock"].overview()}
    assert overview["Amoxicilina Demo"].lotted_quantity == 50 and overview["Amoxicilina Demo"].unlotted_quantity == 0


async def test_full_flow_prescription_to_fefo_dispensation(ctx):
    await receive(ctx, ctx["amoxicillin"], "late", 300, 30)
    await receive(ctx, ctx["amoxicillin"], "early", 30, 8)
    prescription = await ctx["rx"].prescribe(PrescriptionCreateDTO(
        patient_id=ctx["patient"].id, prescriber_id=ctx["doctor"].id, items=[rx_item(ctx["amoxicillin"], 21)]))
    assert prescription.status == PS.ACTIVE and not prescription.special_control
    item_id = prescription.items[0].id

    first = await ctx["rx"].dispense(DispensationCreateDTO(
        prescription_id=prescription.id, pharmacist_id=ctx["pharmacist"].id, location="farmacia_central",
        items=[DispensationItemDTO(prescription_item_id=item_id, quantity=10)]))
    assert [(l.lot_number, l.quantity) for l in first.lines] == [("EARLY", 8), ("LATE", 2)]
    assert first.prescription_status == PS.PARTIALLY_DISPENSED

    with pytest.raises(BusinessRuleViolation, match="restam 11"):
        await ctx["rx"].dispense(DispensationCreateDTO(
            prescription_id=prescription.id, pharmacist_id=ctx["pharmacist"].id, location=LOCATION,
            items=[DispensationItemDTO(prescription_item_id=item_id, quantity=12)]))
    ctx["clock"].now += timedelta(minutes=5)  # segunda dispensação em outro momento
    second = await ctx["rx"].dispense(DispensationCreateDTO(
        prescription_id=prescription.id, pharmacist_id=ctx["pharmacist"].id, location=LOCATION,
        items=[DispensationItemDTO(prescription_item_id=item_id, quantity=11)]))
    assert second.prescription_status == PS.DISPENSED

    aggregate = await ctx["inventory"].get_by_medication_and_location(ctx["amoxicillin"].id, LOCATION)
    assert aggregate.quantity == 38 - 21
    outs = await ctx["stock"].search_movements(MovementFilters(movement_type=MovementType.DISPENSATION))
    assert sum(m.quantity for m in outs.items) == 21 and outs.items[0].reference_id == second.id


async def test_legacy_dispense_is_reconciled_against_lots(ctx):
    medication = ctx["amoxicillin"]
    await receive(ctx, medication, "soon", 20, 10)
    await receive(ctx, medication, "later", 200, 10)
    await ctx["legacy"].dispense_medication(medication.id, LOCATION, 15)  # endpoint legado: só o total muda

    lots = (await ctx["stock"].search_lots(LotFilters(medication_id=medication.id))).items
    assert sum(l.quantity for l in lots) == 20  # ainda desatualizado até a próxima operação nova
    await receive(ctx, medication, "new", 400, 5)  # qualquer operação nova reconcilia antes

    lots = {l.lot_number: l.quantity for l in (await ctx["stock"].search_lots(LotFilters(medication_id=medication.id))).items}
    assert lots == {"LATER": 5, "NEW": 5}  # 15 baixados por FEFO: SOON (10) e 5 de LATER
    adjustments = await ctx["stock"].search_movements(MovementFilters(movement_type=MovementType.ADJUSTMENT))
    assert sum(m.quantity for m in adjustments.items) == 15


async def test_dispensing_never_uses_expired_lots_and_discard_rules(ctx):
    medication = ctx["amoxicillin"]
    lot = await receive(ctx, medication, "short", 2, 10)
    ctx["clock"].now += timedelta(days=5)  # o lote venceu
    prescription = await ctx["rx"].prescribe(PrescriptionCreateDTO(
        patient_id=ctx["patient"].id, prescriber_id=ctx["doctor"].id, items=[rx_item(medication, 5)]))
    with pytest.raises(ConflictError, match="disponível 0"):
        await ctx["rx"].dispense(DispensationCreateDTO(
            prescription_id=prescription.id, pharmacist_id=ctx["pharmacist"].id, location=LOCATION,
            items=[DispensationItemDTO(prescription_item_id=prescription.items[0].id, quantity=5)]))

    expiring = await ctx["stock"].search_lots(LotFilters(expiring_before=ctx["clock"].now.date()))
    assert [l.lot_number for l in expiring.items] == ["SHORT"] and expiring.items[0].is_expired
    discarded = await ctx["stock"].discard_lot(lot.id, None)  # vencido: descarte sem justificativa
    assert discarded.quantity == 0
    valid = await receive(ctx, medication, "valid", 100, 3)
    with pytest.raises(BusinessRuleViolation, match="justificativa"):
        await ctx["stock"].discard_lot(valid.id, "curto")


async def test_prescription_rules(ctx):
    rx, patient = ctx["rx"], ctx["patient"]
    with pytest.raises(BusinessRuleViolation, match="médicos"):
        await rx.prescribe(PrescriptionCreateDTO(patient_id=patient.id, prescriber_id=ctx["nurse"].id,
                                                 items=[rx_item(ctx["amoxicillin"])]))
    with pytest.raises(BusinessRuleViolation, match="controle especial"):
        await rx.prescribe(PrescriptionCreateDTO(patient_id=patient.id, prescriber_id=ctx["doctor"].id,
                                                 items=[rx_item(ctx["clonazepam"], 90)]))
    controlled = await rx.prescribe(PrescriptionCreateDTO(patient_id=patient.id, prescriber_id=ctx["doctor"].id,
                                                          items=[rx_item(ctx["clonazepam"], 30)]))
    assert controlled.special_control

    await ctx["stock"].set_details(ctx["amoxicillin"].id, MedicationDetailsDTO(catalog_status=CatalogStatus.DISCONTINUED))
    with pytest.raises(BusinessRuleViolation, match="descontinuado"):
        await rx.prescribe(PrescriptionCreateDTO(patient_id=patient.id, prescriber_id=ctx["doctor"].id,
                                                 items=[rx_item(ctx["amoxicillin"])]))


async def test_allergy_blocks_prescription_unless_justified(ctx):
    await ctx["records"].add_allergy(ctx["patient"].id, AllergyCreateDTO(
        substance="amoxicilina", category=AllergyCategory.MEDICATION, severity=AllergySeverity.SEVERE))
    request = PrescriptionCreateDTO(patient_id=ctx["patient"].id, prescriber_id=ctx["doctor"].id,
                                    items=[rx_item(ctx["amoxicillin"])])
    with pytest.raises(ConflictError, match="Amoxicilina Demo × amoxicilina"):
        await ctx["rx"].prescribe(request)
    justified = await ctx["rx"].prescribe(request.model_copy(update={
        "allergy_override_reason": "Teste de tolerância supervisionado (fictício)"}))
    assert justified.allergy_override_reason.startswith("Teste")


def test_allergy_text_matching():
    class Med:
        name, generic_name = "Dipirona Demo", "Dipirona sódica"
    assert allergy_matches("dipirona", Med)
    assert not allergy_matches("Penicilina", Med)


async def test_item_lifecycle_patient_medications_and_expiration(ctx):
    rx = ctx["rx"]
    prescription = await rx.prescribe(PrescriptionCreateDTO(
        patient_id=ctx["patient"].id, prescriber_id=ctx["doctor"].id,
        items=[rx_item(ctx["amoxicillin"]), rx_item(ctx["clonazepam"], 10)]))
    first, second = prescription.items
    updated = await rx.change_item(prescription.id, second.id, "suspend", "Sonolência excessiva (fictício)")
    assert updated.items[1].status == ItemStatus.SUSPENDED

    suspended = await rx.patient_medications(ctx["patient"].id, ItemStatus.SUSPENDED)
    assert [m.medication_name for m in suspended] == ["Clonazepam Demo 2mg"]
    with pytest.raises(BusinessRuleViolation, match="em uso"):
        await rx.dispense(DispensationCreateDTO(
            prescription_id=prescription.id, pharmacist_id=ctx["pharmacist"].id, location=LOCATION,
            items=[DispensationItemDTO(prescription_item_id=second.id, quantity=1)]))
    with pytest.raises(BusinessRuleViolation, match="farmacêuticos"):
        await rx.dispense(DispensationCreateDTO(
            prescription_id=prescription.id, pharmacist_id=ctx["doctor"].id, location=LOCATION,
            items=[DispensationItemDTO(prescription_item_id=first.id, quantity=1)]))

    ctx["clock"].now += timedelta(days=31)
    assert (await rx.get(prescription.id)).is_expired
    with pytest.raises(BusinessRuleViolation, match="vencida"):
        await rx.dispense(DispensationCreateDTO(
            prescription_id=prescription.id, pharmacist_id=ctx["pharmacist"].id, location=LOCATION,
            items=[DispensationItemDTO(prescription_item_id=first.id, quantity=1)]))
