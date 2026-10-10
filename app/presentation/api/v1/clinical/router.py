from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.application.dtos.clinical_dto import ClinicalNoteCreateDTO, ClinicalNoteUpdateDTO, ClinicalNoteResponseDTO
from app.application.use_cases.clinical_evolution_use_case import ClinicalEvolutionUseCase
from app.infrastructure.persistence.repositories.sqlalchemy_clinical_repository import SQLAlchemyClinicalRepository
from app.infrastructure.security.permission_checker import PermissionChecker
from app.infrastructure.persistence.database import get_db
from app.application.dtos.schedule_dto import ScheduleResponseDTO
from app.application.use_cases.schedule_use_case import ScheduleUseCase
from app.infrastructure.persistence.repositories.sqlalchemy_schedule_repository import SQLAlchemyScheduleRepository
from app.infrastructure.persistence.models.schedule_model import ScheduleModel
from app.domain.entities.schedule import ScheduleStatus
from app.domain.exceptions.clinical_exceptions import NoteImmutableError, NoteNotFoundError
from app.domain.exceptions.common import ConflictError
from app.application.use_cases.clinical_notes_bridge_use_case import ClinicalNotesBridgeUseCase
from app.application.use_cases.medical_record_use_case import MedicalRecordUseCase
from app.presentation.api.v1.medical_records.router import get_use_case as get_record_use_case

class AppointmentBookingDTO(BaseModel):
    slot_id: uuid.UUID
    patient_id: uuid.UUID

class AvailabilityCreateDTO(BaseModel):
    doctor_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    notes: str | None = None

def schedule_response(item):
    return ScheduleResponseDTO(
        id=item.id, doctor_id=item.doctor_id, patient_id=item.patient_id,
        start_time=item.start_time, end_time=item.end_time,
        status=item.status.value,
        duration_minutes=int((item.end_time-item.start_time).total_seconds() // 60)
    )

router = APIRouter(prefix="/clinical", tags=["Prontuário Clínico"])

async def get_clinical_repo(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyClinicalRepository(session)

async def get_notes_bridge(repo: SQLAlchemyClinicalRepository = Depends(get_clinical_repo),
                           records: MedicalRecordUseCase = Depends(get_record_use_case)):
    # ID de profissional vira evolução clínica; ID de usuário segue o fluxo legado.
    return ClinicalNotesBridgeUseCase(ClinicalEvolutionUseCase(repo), records)

@router.get("/availability", response_model=List[ScheduleResponseDTO])
async def list_available_slots(session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(ScheduleModel)
        .where(ScheduleModel.status == ScheduleStatus.AVAILABLE.value)
        .where(ScheduleModel.start_time >= datetime.now())
        .order_by(ScheduleModel.start_time)
    )
    slots = [SQLAlchemyScheduleRepository(session)._map_to_domain(row) for row in result.scalars().all()]
    return [schedule_response(slot) for slot in slots]

@router.post("/availability", response_model=ScheduleResponseDTO, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(PermissionChecker(["clinical:write"]))])
async def create_available_slot(request: AvailabilityCreateDTO, session: AsyncSession = Depends(get_db)):
    try:
        slot = await ScheduleUseCase(SQLAlchemyScheduleRepository(session)).create_availability_slot(
            request.doctor_id, request.start_time, request.end_time, request.notes
        )
        return schedule_response(slot)
    except Exception as exc:
        from app.domain.exceptions.base import DomainException
        if isinstance(exc, (DomainException, ValueError)):
            raise HTTPException(status_code=400, detail=getattr(exc, "message", str(exc))) from exc
        raise

@router.post("/notes", response_model=ClinicalNoteResponseDTO, status_code=status.HTTP_201_CREATED,
              dependencies=[Depends(PermissionChecker(["clinical:write"]))])
async def create_note(
    request: ClinicalNoteCreateDTO,
    bridge: ClinicalNotesBridgeUseCase = Depends(get_notes_bridge)
):
    return await bridge.create(request)

@router.get("/patients/{patient_id}/history", response_model=List[ClinicalNoteResponseDTO],
             dependencies=[Depends(PermissionChecker(["clinical:read"]))])
async def get_history(
    patient_id: uuid.UUID,
    bridge: ClinicalNotesBridgeUseCase = Depends(get_notes_bridge)
):
    return await bridge.history(patient_id)

@router.get("/patients/{patient_id}/appointments", response_model=List[ScheduleResponseDTO])
async def get_patient_appointments(
    patient_id: uuid.UUID,
    session: AsyncSession = Depends(get_db)
):
    schedule_repo = SQLAlchemyScheduleRepository(session)
    use_case = ScheduleUseCase(schedule_repo)
    schedules = await use_case.get_my_appointments(patient_id)
    return [schedule_response(item) for item in schedules]

@router.post("/schedule", response_model=ScheduleResponseDTO, status_code=status.HTTP_201_CREATED,
             )
async def book_appointment(request: AppointmentBookingDTO, session: AsyncSession = Depends(get_db)):
    try:
        item = await ScheduleUseCase(SQLAlchemyScheduleRepository(session)).book_appointment(
            request.slot_id, request.patient_id
        )
        return schedule_response(item)
    except Exception as exc:
        from app.domain.exceptions.base import DomainException
        if isinstance(exc, DomainException):
            raise HTTPException(status_code=400, detail=exc.message) from exc
        raise

@router.patch("/notes/{note_id}/finalize", response_model=ClinicalNoteResponseDTO,
              dependencies=[Depends(PermissionChecker(["clinical:write"]))])
async def finalize_note(
    note_id: uuid.UUID,
    bridge: ClinicalNotesBridgeUseCase = Depends(get_notes_bridge)
):
    try:
        return await bridge.finalize(note_id)
    except (NoteImmutableError, ConflictError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NoteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota não encontrada")

@router.patch("/notes/{note_id}", response_model=ClinicalNoteResponseDTO,
              dependencies=[Depends(PermissionChecker(["clinical:write"]))])
async def update_note(
    note_id: uuid.UUID,
    request: ClinicalNoteUpdateDTO,
    bridge: ClinicalNotesBridgeUseCase = Depends(get_notes_bridge)
):
    try:
        return await bridge.update(note_id, request)
    except (NoteImmutableError, ConflictError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NoteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota não encontrada")
