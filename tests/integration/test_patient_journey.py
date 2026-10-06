from datetime import date, datetime, timedelta
from decimal import Decimal

from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
from app.infrastructure.persistence.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.persistence.repositories.sqlalchemy_triage_repository import SQLAlchemyTriageRepository
from app.infrastructure.persistence.repositories.sqlalchemy_schedule_repository import SQLAlchemyScheduleRepository
from app.infrastructure.persistence.repositories.sqlalchemy_medication_repository import (
    SQLAlchemyMedicationRepository,
    SQLAlchemyInventoryRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_billing_repository import SQLAlchemyBillingRepository

from app.application.dtos.patient_dto import PatientCreateDTO
from app.application.use_cases.manage_patient_use_case import ManagePatientUseCase
from app.application.use_cases.triage_use_case import TriageUseCase
from app.application.use_cases.schedule_use_case import ScheduleUseCase
from app.application.use_cases.pharmacy_use_case import PharmacyUseCase
from app.application.use_cases.billing_use_case import BillingUseCase

from app.domain.entities.user import User
from app.domain.entities.triage import TriagePriority
from app.domain.entities.schedule import ScheduleStatus
from app.domain.entities.billing import BillingStatus, BillingType


async def test_full_patient_journey(db_session):
    """
    Teste de Integração Ponta-a-Ponta (dados fictícios):
    Paciente -> Triagem -> Agendamento -> Farmácia -> Faturamento.
    """
    user_repo = SQLAlchemyUserRepository(db_session)
    billing_repo = SQLAlchemyBillingRepository(db_session)

    patient_uc = ManagePatientUseCase(SQLAlchemyPatientRepository(db_session))
    triage_uc = TriageUseCase(SQLAlchemyTriageRepository(db_session))
    schedule_uc = ScheduleUseCase(SQLAlchemyScheduleRepository(db_session))
    pharmacy_uc = PharmacyUseCase(SQLAlchemyMedicationRepository(db_session),
                                  SQLAlchemyInventoryRepository(db_session))
    billing_uc = BillingUseCase(billing_repo)

    nurse = await user_repo.save(User(full_name="Enfermeira Ana", email="ana@healthos.example",
                                      cpf="52998224725", password_hash="demo", phone=None))
    doctor = await user_repo.save(User(full_name="Dr. João", email="joao@healthos.example",
                                       cpf="11144477735", password_hash="demo", phone=None))

    patient = await patient_uc.create_patient(PatientCreateDTO(
        full_name="Maria Silva", cpf="39053344705", birth_date=date(1980, 5, 20), gender="Feminino",
    ))

    triage = await triage_uc.perform_triage(
        patient_id=patient.id, nurse_id=nurse.id, priority=TriagePriority.RED,
        main_complaint="Queixa fictícia", blood_pressure="160/100", heart_rate=110,
        temperature=37.5, oxygen_saturation=92, respiratory_rate=22,
    )
    assert triage.priority == TriagePriority.RED

    # Uma segunda triagem do mesmo paciente reclassifica a existente.
    retriage = await triage_uc.perform_triage(
        patient_id=patient.id, nurse_id=nurse.id, priority=TriagePriority.YELLOW,
        main_complaint="Reavaliação fictícia", blood_pressure="130/85", heart_rate=90,
        temperature=37.0, oxygen_saturation=96, respiratory_rate=18,
    )
    assert retriage.id == triage.id
    assert retriage.priority == TriagePriority.YELLOW

    start = datetime.now() + timedelta(hours=1)
    slot = await schedule_uc.create_availability_slot(doctor.id, start, start + timedelta(minutes=30))
    booked = await schedule_uc.book_appointment(slot.id, patient.id)
    assert booked.status == ScheduleStatus.BOOKED

    med = await pharmacy_uc.register_medication(
        name="Medicamento Demo", generic_name="Genérico Demo", dosage="0.5mg", unit="AMPOLA",
    )
    await pharmacy_uc.add_inventory_stock(med.id, "FARMACIA_CENTRAL", 100)
    await pharmacy_uc.add_inventory_stock(med.id, "FARMACIA_CENTRAL", 10)
    await pharmacy_uc.dispense_medication(med.id, "FARMACIA_CENTRAL", 1)

    status = await pharmacy_uc.get_stock_status(med.id, "FARMACIA_CENTRAL")
    assert status["quantity"] == 109

    invoice = await billing_uc.create_invoice(
        patient_id=patient.id, invoice_number="INV-2026-001",
        insurance_provider="Convênio Fictício", insurance_coverage=Decimal("80.00"),
    )
    await billing_uc.add_charge_to_invoice(
        invoice.id, "Consulta de Emergência", BillingType.URGENCY_FEE, Decimal("1.0"), Decimal("250.00"),
    )
    await billing_uc.add_charge_to_invoice(
        invoice.id, "Medicamento", BillingType.MEDICATION, Decimal("1.0"), Decimal("15.00"),
    )
    final_invoice = await billing_uc.finalize_invoice(invoice.id)
    assert final_invoice.status == BillingStatus.PENDING

    # Coparticipação: total 265.00 com 80% de cobertura => paciente paga 53.00
    summary = await billing_uc.get_patient_financial_summary(patient.id)
    assert len(summary) == 1
    assert summary[0]["patient_share"] == Decimal("53.00")

    await billing_uc.record_payment(final_invoice.id)
    updated_invoice = await billing_repo.get_invoice_by_id(final_invoice.id)
    assert updated_invoice.status == BillingStatus.PAID
    assert len(updated_invoice.items) == 2
