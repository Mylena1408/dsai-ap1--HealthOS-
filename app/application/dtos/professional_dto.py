from datetime import time
from typing import Optional
import uuid

from pydantic import BaseModel, EmailStr, Field

from app.domain.entities.professional import ProfessionalStatus, ProfessionalType


class DepartmentCreateDTO(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    description: Optional[str] = Field(None, max_length=500)


class DepartmentResponseDTO(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]


class SpecialtyCreateDTO(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    default_duration_minutes: int = Field(30, ge=10, le=240)


class SpecialtyResponseDTO(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    default_duration_minutes: int


class WorkingHoursDTO(BaseModel):
    weekday: int = Field(..., ge=0, le=6, description="0 = segunda ... 6 = domingo")
    start_time: time
    end_time: time


class ProfessionalCreateDTO(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=255)
    professional_type: ProfessionalType
    registry_number: str = Field(..., min_length=3, max_length=50, description="Registro fictício, ex.: CRM-PA 12345")
    department_id: Optional[uuid.UUID] = None
    specialty_id: Optional[uuid.UUID] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    bio: Optional[str] = Field(None, max_length=1000)
    working_hours: list[WorkingHoursDTO] = Field(default_factory=list)


class ProfessionalUpdateDTO(BaseModel):
    full_name: Optional[str] = Field(None, min_length=3, max_length=255)
    department_id: Optional[uuid.UUID] = None
    specialty_id: Optional[uuid.UUID] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    bio: Optional[str] = Field(None, max_length=1000)
    status: Optional[ProfessionalStatus] = None


class ProfessionalResponseDTO(BaseModel):
    id: uuid.UUID
    full_name: str
    professional_type: ProfessionalType
    registry_number: str
    department_id: Optional[uuid.UUID]
    department_name: Optional[str]
    specialty_id: Optional[uuid.UUID]
    specialty_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    status: ProfessionalStatus
    bio: Optional[str]
    working_hours: list[WorkingHoursDTO]
