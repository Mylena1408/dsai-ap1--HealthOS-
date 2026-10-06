from datetime import datetime, timedelta
import uuid

import pytest
from sqlalchemy import func, select

from app.application.services.stock_service import StockService
from app.application.use_cases.appointment_use_case import AppointmentUseCase
from app.application.use_cases.dashboard_use_case import DashboardDeps, DashboardUseCase, daily_series, last_months
from app.application.use_cases.laboratory_use_case import LaboratoryUseCase
from app.application.use_cases.pharmacy_stock_use_case import PharmacyStockUseCase
from app.application.use_cases.prescription_use_case import PrescriptionUseCase
from app.application.use_cases.vital_signs_use_case import VitalSignsUseCase
from app.domain.exceptions.common import EntityNotFoundError
from app.infrastructure.persistence.models.appointment_model import AppointmentModel
from app.infrastructure.persistence.models.patient_model import PatientModel
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

NOW = datetime(2026, 10, 6, 12, 0)


@pytest.fixture
async def ctx(db_session):
    await seed_demo_data(db_session, patients=15, appointments=60, exams=40, prescriptions=20, now=NOW)
    clock = lambda: NOW  # noqa: E731
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


async def test_health_inputs_match_the_database(ctx):
    session, analytics = ctx["session"], ctx["analytics"]
    inputs = await analytics.health_inputs(NOW)
    assert len(inputs) == await session.scalar(select(func.count()).select_from(PatientModel))

    completed = await session.scalar(select(func.count()).select_from(AppointmentModel).where(
        AppointmentModel.status == "FINALIZADA", AppointmentModel.start_time >= NOW - timedelta(days=365),
        AppointmentModel.start_time <= NOW))
    assert sum(i.completed_appointments for i in inputs.values()) == completed
    assert all(i.dispensed_quantity <= i.prescribed_quantity + 1e-9 for i in inputs.values())
    assert all(i.exams_released <= i.exams_requested for i in inputs.values())

    one = next(iter(inputs))
    assert (await analytics.health_inputs(NOW, {one}))[one] == inputs[one]  # lote e individual coincidem


async def test_patient_dashboard_and_health_score(ctx):
    patient_id = (await ctx["session"].scalars(select(PatientModel.id))).first()
    board = await ctx["use_case"].patient(patient_id)
    assert board.health_score.patient_id == patient_id
    assert len(board.health_score.components) == 5
    assert "Não é diagnóstico" in board.health_score.disclaimer
    assert all(a.start_time >= NOW for a in board.upcoming_appointments)
    assert all(e.status.value == "LIBERADO" for e in board.recent_exams)
    with pytest.raises(EntityNotFoundError):
        await ctx["use_case"].patient(uuid.uuid4())


async def test_professional_dashboard(ctx):
    doctor_id = (await ctx["session"].scalars(
        select(AppointmentModel.professional_id).where(AppointmentModel.status == "FINALIZADA"))).first()
    board = await ctx["use_case"].professional(doctor_id)
    assert len(board.daily_30d) == 30 and board.daily_30d[-1].day == NOW.date()
    total_in_series = sum(sum(p.values.values()) for p in board.daily_30d)
    tracked = sum(board.appointments_30d.get(k, 0) for k in ("FINALIZADA", "CANCELADA", "NAO_COMPARECEU"))
    assert total_in_series == tracked
    if board.attendance_rate_30d is not None:
        assert 0 <= board.attendance_rate_30d <= 1
    assert all(e.requested_by == doctor_id for e in board.recent_abnormal_exams)


async def test_pharmacy_and_admin_dashboards(ctx):
    pharmacy = await ctx["use_case"].pharmacy()
    assert pharmacy.items_below_minimum > 0  # o seed deixa itens críticos de propósito
    assert sum(p.values["unidades"] for p in pharmacy.daily_30d) == pharmacy.units_dispensed_30d
    assert len(pharmacy.top_medications_30d) <= 5

    admin = await ctx["use_case"].admin()
    assert admin.counts["patients"] == 15
    assert sum(admin.health_score_distribution.values()) == 15
    assert [m.label for m in admin.new_patients_monthly][-1] == NOW.strftime("%m/%Y")
    assert set(admin.alerts_open) == {"by_category", "by_level"}


def test_series_helpers():
    start = NOW.date() - timedelta(days=2)
    series = daily_series([(NOW, "A"), (NOW, "A"), (NOW - timedelta(days=2), "B")], start, 3, ["A", "B"])
    assert [p.values for p in series] == [{"A": 0, "B": 1}, {"A": 0, "B": 0}, {"A": 2, "B": 0}]
    assert [m.month for m in last_months(NOW.date(), 3)] == [8, 9, 10]
