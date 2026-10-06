"""Painéis por perfil e Health Score (indicador demonstrativo)."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.dashboard_dto import (
    AdminDashboardDTO, HealthScoreDTO, PatientDashboardDTO, PharmacyDashboardDTO, ProfessionalDashboardDTO,
)
from app.application.use_cases.dashboard_use_case import DashboardDeps, DashboardUseCase
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.sqlalchemy_analytics_repository import SQLAlchemyAnalyticsRepository
from app.infrastructure.persistence.repositories.sqlalchemy_engagement_repository import (
    SQLAlchemyInboxRepository, SQLAlchemySystemAlertRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_medical_record_repository import (
    SQLAlchemyPatientDirectoryRepository,
)
from app.presentation.api.v1.appointments.router import get_use_case as get_appointments
from app.presentation.api.v1.clinical_monitoring.router import get_lab, get_vitals
from app.presentation.api.v1.pharmacy_v2.router import get_prescriptions, get_stock

router = APIRouter(tags=["Painéis e Indicadores"])


async def get_dashboards(session: AsyncSession = Depends(get_db), appointments=Depends(get_appointments),
                         laboratory=Depends(get_lab), vitals=Depends(get_vitals),
                         prescriptions=Depends(get_prescriptions), stock=Depends(get_stock)) -> DashboardUseCase:
    return DashboardUseCase(DashboardDeps(
        analytics=SQLAlchemyAnalyticsRepository(session), directory=SQLAlchemyPatientDirectoryRepository(session),
        professional_repo=appointments.professional_repo, alerts=SQLAlchemySystemAlertRepository(session),
        inbox=SQLAlchemyInboxRepository(session), appointments=appointments, laboratory=laboratory, vitals=vitals,
        prescriptions=prescriptions, stock=stock))


Dashboards = Depends(get_dashboards)


@router.get("/patients/{patient_id}/health-score", response_model=HealthScoreDTO,
            summary="Health Score: indicador demonstrativo de acompanhamento (não é diagnóstico)")
async def health_score(patient_id: uuid.UUID, use_case: DashboardUseCase = Dashboards):
    return await use_case.health_score(patient_id)


@router.get("/dashboards/patient/{patient_id}", response_model=PatientDashboardDTO)
async def patient_dashboard(patient_id: uuid.UUID, use_case: DashboardUseCase = Dashboards):
    return await use_case.patient(patient_id)


@router.get("/dashboards/professional/{professional_id}", response_model=ProfessionalDashboardDTO)
async def professional_dashboard(professional_id: uuid.UUID, use_case: DashboardUseCase = Dashboards):
    return await use_case.professional(professional_id)


@router.get("/dashboards/pharmacy", response_model=PharmacyDashboardDTO)
async def pharmacy_dashboard(use_case: DashboardUseCase = Dashboards):
    return await use_case.pharmacy()


@router.get("/dashboards/admin", response_model=AdminDashboardDTO)
async def admin_dashboard(use_case: DashboardUseCase = Dashboards):
    return await use_case.admin()
