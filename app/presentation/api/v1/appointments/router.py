from datetime import date, datetime, time
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.appointment_dto import (
    AppointmentCancelDTO, AppointmentCompleteDTO, AppointmentCreateDTO, AppointmentRescheduleDTO,
    AppointmentResponseDTO, AvailableSlotDTO,
)
from app.application.dtos.common import Page
from app.application.interfaces.appointment_repository import AppointmentFilters
from app.application.use_cases.appointment_use_case import AppointmentUseCase
from app.domain.entities.appointment import AppointmentStatus
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.persistence.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyCatalogRepository, SQLAlchemyProfessionalRepository,
)

router = APIRouter(tags=["Consultas"])


async def get_use_case(session: AsyncSession = Depends(get_db)) -> AppointmentUseCase:
    return AppointmentUseCase(
        SQLAlchemyAppointmentRepository(session), SQLAlchemyProfessionalRepository(session),
        SQLAlchemyCatalogRepository(session), SQLAlchemyPatientRepository(session),
    )


@router.get("/professionals/{professional_id}/availability", response_model=list[AvailableSlotDTO],
            summary="Horários livres do profissional (expediente menos consultas ativas)")
async def professional_availability(
    professional_id: uuid.UUID,
    date_from: Optional[date] = Query(None, description="Padrão: hoje"),
    days: int = Query(7, ge=1, le=31),
    duration_minutes: Optional[int] = Query(None, ge=10, le=240),
    use_case: AppointmentUseCase = Depends(get_use_case),
):
    start = datetime.combine(date_from or date.today(), time.min)
    return await use_case.available_slots(professional_id, start, days, duration_minutes)


@router.get("/appointments", response_model=Page[AppointmentResponseDTO])
async def search_appointments(
    patient_id: Optional[uuid.UUID] = None,
    professional_id: Optional[uuid.UUID] = None,
    status_: Optional[list[AppointmentStatus]] = Query(None, alias="status", description="Pode ser repetido"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = Query(None, description="Inclusivo"),
    newest_first: bool = False,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    use_case: AppointmentUseCase = Depends(get_use_case),
):
    return await use_case.search(AppointmentFilters(
        patient_id=patient_id, professional_id=professional_id, statuses=status_ or [],
        date_from=datetime.combine(date_from, time.min) if date_from else None,
        date_to=datetime.combine(date_to, time.max) if date_to else None,
        newest_first=newest_first, limit=limit, offset=offset,
    ))


@router.post("/appointments", response_model=AppointmentResponseDTO, status_code=status.HTTP_201_CREATED)
async def book_appointment(request: AppointmentCreateDTO, use_case: AppointmentUseCase = Depends(get_use_case)):
    return await use_case.book(request)


@router.get("/appointments/{appointment_id}", response_model=AppointmentResponseDTO)
async def get_appointment(appointment_id: uuid.UUID, use_case: AppointmentUseCase = Depends(get_use_case)):
    return await use_case.get(appointment_id)


@router.post("/appointments/{appointment_id}/confirm", response_model=AppointmentResponseDTO)
async def confirm_appointment(appointment_id: uuid.UUID, use_case: AppointmentUseCase = Depends(get_use_case)):
    return await use_case.confirm(appointment_id)


@router.post("/appointments/{appointment_id}/start", response_model=AppointmentResponseDTO)
async def start_appointment(appointment_id: uuid.UUID, use_case: AppointmentUseCase = Depends(get_use_case)):
    return await use_case.start(appointment_id)


@router.post("/appointments/{appointment_id}/complete", response_model=AppointmentResponseDTO)
async def complete_appointment(appointment_id: uuid.UUID, request: Optional[AppointmentCompleteDTO] = None,
                               use_case: AppointmentUseCase = Depends(get_use_case)):
    return await use_case.complete(appointment_id, request.notes if request else None)


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentResponseDTO)
async def cancel_appointment(appointment_id: uuid.UUID, request: AppointmentCancelDTO,
                             use_case: AppointmentUseCase = Depends(get_use_case)):
    return await use_case.cancel(appointment_id, request.reason)


@router.post("/appointments/{appointment_id}/no-show", response_model=AppointmentResponseDTO)
async def mark_no_show(appointment_id: uuid.UUID, use_case: AppointmentUseCase = Depends(get_use_case)):
    return await use_case.mark_no_show(appointment_id)


@router.post("/appointments/{appointment_id}/reschedule", response_model=AppointmentResponseDTO)
async def reschedule_appointment(appointment_id: uuid.UUID, request: AppointmentRescheduleDTO,
                                 use_case: AppointmentUseCase = Depends(get_use_case)):
    return await use_case.reschedule(appointment_id, request.start_time, request.duration_minutes)
