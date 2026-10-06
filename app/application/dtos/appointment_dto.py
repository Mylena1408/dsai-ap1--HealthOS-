from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field

from app.domain.entities.appointment import AppointmentStatus, AppointmentType


class AppointmentCreateDTO(BaseModel):
    patient_id: uuid.UUID
    professional_id: uuid.UUID
    start_time: datetime
    duration_minutes: Optional[int] = Field(None, description="Padrão: duração da especialidade (ou 30 min)")
    appointment_type: AppointmentType = AppointmentType.FIRST_VISIT
    specialty_id: Optional[uuid.UUID] = None
    reason: Optional[str] = Field(None, max_length=500)


class AppointmentCancelDTO(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class AppointmentCompleteDTO(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


class AppointmentRescheduleDTO(BaseModel):
    start_time: datetime
    duration_minutes: Optional[int] = None


class StatusChangeDTO(BaseModel):
    from_status: Optional[AppointmentStatus]
    to_status: AppointmentStatus
    changed_at: datetime
    note: Optional[str]


class AppointmentResponseDTO(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: Optional[str]
    professional_id: uuid.UUID
    professional_name: Optional[str]
    specialty_id: Optional[uuid.UUID]
    appointment_type: AppointmentType
    status: AppointmentStatus
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    reason: Optional[str]
    notes: Optional[str]
    cancellation_reason: Optional[str]
    allowed_transitions: list[AppointmentStatus]
    history: list[StatusChangeDTO]


class AvailableSlotDTO(BaseModel):
    start_time: datetime
    end_time: datetime
