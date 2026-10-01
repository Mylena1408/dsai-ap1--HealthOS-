import pytest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.persistence.models.user_model import Base
from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
from app.infrastructure.persistence.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.persistence.repositories.sqlalchemy_triage_repository import SQLAlchemyTriageRepository
from app.infrastructure.persistence.repositories.sqlalchemy_schedule_repository import SQLAlchemyScheduleRepository
from app.infrastructure.persistence.repositories.sqlalchemy_medication_repository import SQLAlchemyMedicationRepository
from app.infrastructure.persistence.repositories.sqlalchemy_billing_repository import SQLAlchemyBillingRepository

from app.application.use_cases.manage_patient_use_case import ManagePatientUseCase
from app.application.use_cases.triage_use_case import TriageUseCase
from app.application.use_cases.schedule_use_case import ScheduleUseCase
from app.application.use_cases.pharmacy_use_case import PharmacyUseCase
from app.application.use_cases.billing_use_case import BillingUseCase

from app.domain.entities.triage import TriagePriority

# Configuração de Banco de Dados em Memória para Testes
DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture(asyncio=True)
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        yield session
        await session.commit()

@pytest.mark.asyncio
async def test_full_patient_journey(db_session):
    """
    Teste de Integração Ponta-a-Ponta:
    Paciente -> Triagem -> Agendamento -> Prescrição/Farmácia -> Faturamento.
    """
    # 1. Setup de Repositórios e Use Cases
    user_repo = SQLAlchemyUserRepository(db_session)
    patient_repo = SQLAlchemyPatientRepository(db_session)
    triage_repo = SQLAlchemyTriageRepository(db_session)
    schedule_repo = SQLAlchemyScheduleRepository(db_session)
    med_repo = SQLAlchemyMedicationRepository(db_session)
    inv_repo = SQLAlchemyInventoryRepository(db_session) # Precisamos importar a implementação
    billing_repo = SQLAlchemyBillingRepository(db_session)

    patient_uc = ManagePatientUseCase(patient_repo)
    triage_uc = TriageUseCase(triage_repo)
    schedule_uc = ScheduleUseCase(schedule_repo)
    pharmacy_uc = PharmacyUseCase(med_repo, inv_repo)
    billing_uc = BillingUseCase(billing_repo)

    # 2. Criação de Usuários (Médico e Enfermeiro)
    nurse = await user_repo.save(User(name="Enfermeiro Ana", email="ana@hospital.com", role="NURSE"))
    doctor = await user_repo.save(User(name="Dr. Silva", email="silva@hospital.com", role="DOCTOR"))

    # 3. Fluxo do Paciente: Cadastro e Triagem
    patient = await patient_uc.create_patient(
        name="João da Silva",
        cpf="12345678901",
        birth_date=datetime(1980, 5, 20)
    )

    triage = await triage_uc.perform_triage(
        patient_id=patient.id,
        nurse_id=nurse.id,
        priority=TriagePriority.RED,
        main_complaint="Dor torácica aguda",
        blood_pressure="160/100",
        heart_rate=110,
        temperature=37.5,
        oxygen_saturation=92,
        respiratory_rate=22
    )
    assert triage.priority == TriagePriority.RED

    # 4. Agendamento de Emergência
    start = datetime.now() + timedelta(minutes=10)
    end = start + timedelta(minutes=30)
    slot = await schedule_uc.create_availability_slot(doctor.id, start, end)
    booked = await schedule_uc.book_appointment(slot.id, patient.id)
    assert booked.status == ScheduleStatus.BOOKED

    # 5. Prescrição e Dispensação de Medicamentos
    med = await pharmacy_uc.register_medication(
        name="Atropina", generic_name="Atropina Sulfato",
        dosage="0.5mg", unit="AMPOLA"
    )
    await pharmacy_uc.add_inventory_stock(med.id, "FARMACIA_CENTRAL", 100)

    # Dispensação para o paciente
    await pharmacy_uc.dispense_medication(med.id, "FARMACIA_CENTRAL", 1)

    # Verificar estoque
    status = await pharmacy_uc.get_stock_status(med.id, "FARMACIA_CENTRAL")
    assert status["quantity"] == 99

    # 6. Faturamento do Atendimento
    invoice = await billing_uc.create_invoice(
        patient_id=patient.id,
        invoice_number="INV-2026-001",
        insurance_provider="SaúdeTotal",
        insurance_coverage=Decimal("80.00")
    )

    await billing_uc.add_charge_to_invoice(
        invoice.id, "Consulta de Emergência", BillingType.URGENCY_FEE,
        Decimal("1.0"), Decimal("250.00")
    )
    await billing_uc.add_charge_to_invoice(
        invoice.id, "Medicamento Atropina", BillingType.MEDICATION,
        Decimal("1.0"), Decimal("15.00")
    )

    final_invoice = await billing_uc.finalize_invoice(invoice.id)

    # Cálculo de Coparticipação: Total (265.00) * 20% = 53.00
    summary = await billing_uc.get_patient_financial_summary(patient.id)
    assert summary[0]["patient_share"] == Decimal("53.00")
    assert final_invoice.status == BillingStatus.PENDING

    # 7. Fechamento Financeiro
    await billing_uc.record_payment(final_invoice.id)
    updated_invoice = await billing_repo.get_invoice_by_id(final_invoice.id)
    assert updated_invoice.status == BillingStatus.PAID
