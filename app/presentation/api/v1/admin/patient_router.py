from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.application.dtos.patient_dto import PatientCreateDTO, PatientUpdateDTO, PatientResponseDTO
from app.application.use_cases.manage_patient_use_case import ManagePatientUseCase
from app.infrastructure.persistence.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.security.permission_checker import PermissionChecker
from app.domain.exceptions.base import DomainException
from app.infrastructure.persistence.database import get_db
from app.presentation.api.dependencies import get_events

router = APIRouter(tags=["Gestão de Pacientes"])

async def get_patient_repo(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyPatientRepository(session)

@router.post("/", response_model=PatientResponseDTO, status_code=status.HTTP_201_CREATED,
              dependencies=[]) # Removed admin permission for registration to allow self-registration in demo
async def create_patient(
    request: PatientCreateDTO,
    repo: SQLAlchemyPatientRepository = Depends(get_patient_repo),
    events=Depends(get_events),
):
    try:
        use_case = ManagePatientUseCase(repo, events)
        return await use_case.create_patient(request)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.get("/", response_model=List[PatientResponseDTO],
             dependencies=[Depends(PermissionChecker(["patient:read"]))])
async def list_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    repo: SQLAlchemyPatientRepository = Depends(get_patient_repo)
):
    use_case = ManagePatientUseCase(repo)
    return await use_case.list_patients(skip=skip, limit=limit)

@router.get("/{patient_id}", response_model=PatientResponseDTO,
             dependencies=[Depends(PermissionChecker(["patient:read"]))])
async def get_patient(
    patient_id: uuid.UUID,
    repo: SQLAlchemyPatientRepository = Depends(get_patient_repo)
):
    try:
        use_case = ManagePatientUseCase(repo)
        return await use_case.get_patient_by_id(patient_id)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)

@router.patch("/{patient_id}", response_model=PatientResponseDTO,
              dependencies=[Depends(PermissionChecker(["patient:update"]))])
async def update_patient(
    patient_id: uuid.UUID,
    request: PatientUpdateDTO,
    repo: SQLAlchemyPatientRepository = Depends(get_patient_repo)
):
    try:
        use_case = ManagePatientUseCase(repo)
        return await use_case.update_patient(patient_id, request)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
