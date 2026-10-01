from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.application.dtos.alert_dto import PatientAlertCreateDTO, PatientAlertUpdateDTO, PatientAlertResponseDTO
from app.application.use_cases.manage_alerts_use_case import ManageAlertsUseCase
from app.infrastructure.persistence.repositories.sqlalchemy_alert_repository import SQLAlchemyAlertRepository
from app.infrastructure.security.permission_checker import PermissionChecker
from app.infrastructure.persistence.database import get_db

router = APIRouter(prefix="/alerts", tags=["Alertas de Pacientes"])

async def get_alert_repo(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyAlertRepository(session)

@router.post("/", response_model=PatientAlertResponseDTO, status_code=status.HTTP_201_CREATED,
              dependencies=[Depends(PermissionChecker(["patient:write"]))])
async def create_alert(
    request: PatientAlertCreateDTO,
    repo: SQLAlchemyAlertRepository = Depends(get_alert_repo)
):
    try:
        use_case = ManageAlertsUseCase(repo)
        return await use_case.create_alert(request)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.get("/patient/{patient_id}/active", response_model=List[PatientAlertResponseDTO],
             dependencies=[Depends(PermissionChecker(["patient:read"]))])
async def list_active_alerts(
    patient_id: uuid.UUID,
    repo: SQLAlchemyAlertRepository = Depends(get_alert_repo)
):
    use_case = ManageAlertsUseCase(repo)
    return await use_case.list_active_alerts(patient_id)
