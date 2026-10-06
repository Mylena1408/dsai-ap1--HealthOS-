"""Fixtures compartilhadas pelos testes de integração."""
from datetime import datetime

import pytest

from app.application.services.stock_service import StockService
from app.application.use_cases.appointment_use_case import AppointmentUseCase
from app.application.use_cases.dashboard_use_case import DashboardDeps, DashboardUseCase
from app.application.use_cases.laboratory_use_case import LaboratoryUseCase
from app.application.use_cases.pharmacy_stock_use_case import PharmacyStockUseCase
from app.application.use_cases.prescription_use_case import PrescriptionUseCase
from app.application.use_cases.vital_signs_use_case import VitalSignsUseCase
from app.infrastructure.persistence.repositories.sqlalchemy_analytics_repository import SQLAlchemyAnalyticsRepository
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.persistence.repositories.sqlalchemy_clinical_monitoring_repository import (
    SQLAlchemyLaboratoryRepository, SQLAlchemyVitalSignsRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_engagement_repository import (
    SQLAlchemyInboxRepository, SQLAlchemySystemAlertRepository,
)
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
from app.infrastructure.seed.demo_seed import seed_demo_data




SEED_NOW = datetime(2026, 10, 6, 12, 0)


@pytest.fixture
async def seeded(db_session):
    """Banco semeado com data fixa e os casos de uso montados com o mesmo relógio."""
    await seed_demo_data(db_session, patients=15, appointments=60, exams=40, prescriptions=20, now=SEED_NOW)
    clock = lambda: SEED_NOW  # noqa: E731
    s = db_session
    professionals = SQLAlchemyProfessionalRepository(s)
    directory = SQLAlchemyPatientDirectoryRepository(s)
    pharmacy = SQLAlchemyPharmacyRepository(s)
    stock = StockService(pharmacy, SQLAlchemyInventoryRepository(s))
    deps = DashboardDeps(
        analytics=SQLAlchemyAnalyticsRepository(s), directory=directory, professional_repo=professionals,
        alerts=SQLAlchemySystemAlertRepository(s), inbox=SQLAlchemyInboxRepository(s),
        appointments=AppointmentUseCase(SQLAlchemyAppointmentRepository(s), professionals,
                                        SQLAlchemyCatalogRepository(s), SQLAlchemyPatientRepository(s), clock=clock),
        laboratory=LaboratoryUseCase(SQLAlchemyLaboratoryRepository(s), directory, professionals,
                                     SQLAlchemyAppointmentRepository(s), clock=clock),
        vitals=VitalSignsUseCase(SQLAlchemyVitalSignsRepository(s), directory, professionals, clock=clock),
        prescriptions=PrescriptionUseCase(pharmacy, directory, professionals, SQLAlchemyAppointmentRepository(s),
                                          SQLAlchemyMedicalRecordRepository(s), stock, clock=clock),
        stock=PharmacyStockUseCase(pharmacy, stock, SQLAlchemyMedicationRepository(s), clock=clock),
    )
    return dict(session=s, use_case=DashboardUseCase(deps, clock=clock), analytics=deps.analytics)

