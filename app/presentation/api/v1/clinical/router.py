from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.application.dtos.clinical_dto import ClinicalNoteCreateDTO, ClinicalNoteUpdateDTO, ClinicalNoteResponseDTO
from app.application.use_cases.clinical_evolution_use_case import ClinicalEvolutionUseCase
from app.infrastructure.persistence.repositories.sqlalchemy_clinical_repository import SQLAlchemyClinicalRepository
from app.infrastructure.security.permission_checker import PermissionChecker
from app.infrastructure.persistence.database import get_db

router = APIRouter(prefix="/clinical", tags=["Prontuário Clínico"])

async def get_clinical_repo(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyClinicalRepository(session)

@router.post("/notes", response_model=ClinicalNoteResponseDTO, status_code=status.HTTP_201_CREATED,
              dependencies=[Depends(PermissionChecker(["clinical:write"]))])
async def create_note(
    request: ClinicalNoteCreateDTO,
    repo: SQLAlchemyClinicalRepository = Depends(get_clinical_repo)
):
    use_case = ClinicalEvolutionUseCase(repo)
    return await use_case.create_note(request)

@router.get("/patients/{patient_id}/history", response_model=List[ClinicalNoteResponseDTO],
             dependencies=[Depends(PermissionChecker(["clinical:read"]))])
async def get_history(
    patient_id: uuid.UUID,
    repo: SQLAlchemyClinicalRepository = Depends(get_clinical_repo)
):
    use_case = ClinicalEvolutionUseCase(repo)
    return await use_case.get_patient_history(patient_id)

@router.get("/patients/{patient_id}/appointments", response_model=List[ScheduleResponseDTO],
             dependencies=[Depends(PermissionChecker(["clinical:read"]))])
async def get_patient_appointments(
    patient_id: uuid.UUID,
    session: AsyncSession = Depends(get_db)
):
    from app.infrastructure.persistence.repositories.sqlalchemy_schedule_repository import SQLAlchemyScheduleRepository
    schedule_repo = SQLAlchemyScheduleRepository(session)
    # Note: in a real app, we'd use a proper dependency for schedule_repo
    from app.application.use_cases.schedule_use_case import ScheduleUseCase
    use_case = ScheduleUseCase(schedule_repo)
    return await use_case.get_my_appointments(patient_id)

@router.patch("/notes/{note_id}/finalize", response_model=ClinicalNoteResponseDTO,
              dependencies=[Depends(PermissionChecker(["clinical:write"]))])
async def finalize_note(
    note_id: uuid.UUID,
    repo: SQLAlchemyClinicalRepository = Depends(get_clinical_repo)
):
    try:
        use_case = ClinicalEvolutionUseCase(repo)
        return await use_case.finalize_note(note_id)
    except NoteImmutableError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NoteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota não encontrada")

@router.patch("/notes/{note_id}", response_model=ClinicalNoteResponseDTO,
              dependencies=[Depends(PermissionChecker(["clinical:write"]))])
async def update_note(
    note_id: uuid.UUID,
    request: ClinicalNoteUpdateDTO,
    repo: SQLAlchemyClinicalRepository = Depends(get_clinical_repo)
):
    try:
        use_case = ClinicalEvolutionUseCase(repo)
        return await use_case.update_draft(note_id, request)
    except NoteImmutableError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NoteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota não encontrada")
