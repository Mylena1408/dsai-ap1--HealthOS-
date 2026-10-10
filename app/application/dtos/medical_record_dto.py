from datetime import date, datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field

from app.application.dtos.appointment_dto import AppointmentResponseDTO
from app.application.dtos.patient_dto import PatientResponseDTO
from app.domain.entities.medical_record import (
    EVOLUTION_MAX_LENGTH, EVOLUTION_MIN_LENGTH, AllergyCategory, AllergySeverity, AllergyStatus, BloodType,
    ConditionStatus, DiagnosisCertainty, DiagnosisType, EvolutionStatus,
)
from app.domain.entities.timeline import TimelineEventType


class PatientListItemDTO(BaseModel):
    id: uuid.UUID
    full_name: str
    cpf: str
    birth_date: date
    age: int
    gender: str
    phone: Optional[str]
    insurance_provider: Optional[str]


# ------------------------------------------------------------------ perfil

class EmergencyContactCreateDTO(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=255)
    relationship: str = Field(..., min_length=2, max_length=50)
    phone: str = Field(..., min_length=10, max_length=20)
    is_primary: bool = False


class EmergencyContactDTO(EmergencyContactCreateDTO):
    id: uuid.UUID


class ProfileUpdateDTO(BaseModel):
    blood_type: BloodType = BloodType.UNKNOWN
    occupation: Optional[str] = Field(None, max_length=120)
    notes: Optional[str] = Field(None, max_length=2000)


class ProfileDTO(BaseModel):
    blood_type: BloodType
    occupation: Optional[str]
    notes: Optional[str]
    emergency_contacts: list[EmergencyContactDTO]
    updated_at: Optional[datetime]


# ---------------------------------------------------------------- alergias

class AllergyCreateDTO(BaseModel):
    substance: str = Field(..., min_length=2, max_length=120)
    category: AllergyCategory
    severity: AllergySeverity
    reaction: Optional[str] = Field(None, max_length=500)


class AllergyDTO(AllergyCreateDTO):
    id: uuid.UUID
    status: AllergyStatus
    recorded_at: datetime
    resolved_at: Optional[datetime]


# --------------------------------------------------------------- condições

class ConditionCreateDTO(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    code: Optional[str] = Field(None, max_length=20)
    onset_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=1000)


class ConditionStatusDTO(BaseModel):
    status: ConditionStatus


class ConditionDTO(ConditionCreateDTO):
    id: uuid.UUID
    status: ConditionStatus
    resolved_date: Optional[date]
    recorded_at: datetime


# ------------------------------------------------------------ diagnósticos

class DiagnosisCreateDTO(BaseModel):
    description: str = Field(..., min_length=3, max_length=500)
    code: Optional[str] = Field(None, max_length=20)
    diagnosis_type: DiagnosisType = DiagnosisType.PRIMARY
    certainty: DiagnosisCertainty = DiagnosisCertainty.SUSPECTED
    professional_id: Optional[uuid.UUID] = None
    appointment_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(None, max_length=1000)


class DiagnosisDTO(DiagnosisCreateDTO):
    id: uuid.UUID
    professional_name: Optional[str]
    diagnosed_at: datetime


# ----------------------------------------------------------- procedimentos

class ProcedureCreateDTO(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    performed_at: datetime
    professional_id: Optional[uuid.UUID] = None
    appointment_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(None, max_length=1000)


class ProcedureDTO(ProcedureCreateDTO):
    id: uuid.UUID
    professional_name: Optional[str]


# --------------------------------------------------------------- evoluções

class EvolutionCreateDTO(BaseModel):
    professional_id: uuid.UUID
    content: str = Field(..., min_length=EVOLUTION_MIN_LENGTH, max_length=EVOLUTION_MAX_LENGTH)
    appointment_id: Optional[uuid.UUID] = None


class EvolutionUpdateDTO(BaseModel):
    content: str = Field(..., min_length=EVOLUTION_MIN_LENGTH, max_length=EVOLUTION_MAX_LENGTH)


class EvolutionDTO(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    professional_id: uuid.UUID
    professional_name: Optional[str]
    professional_type: Optional[str]
    appointment_id: Optional[uuid.UUID]
    content: str
    status: EvolutionStatus
    version: int
    created_at: datetime
    updated_at: Optional[datetime]
    signed_at: Optional[datetime]


# ------------------------------------------------------- visão consolidada

class TimelineEventDTO(BaseModel):
    occurred_at: datetime
    event_type: TimelineEventType
    title: str
    description: Optional[str]
    status: Optional[str]
    source_id: uuid.UUID


class MedicalRecordDTO(BaseModel):
    """Resumo do prontuário: o que um profissional precisa ver primeiro."""
    patient: PatientResponseDTO
    age: int
    profile: ProfileDTO
    active_allergies: list[AllergyDTO]
    active_conditions: list[ConditionDTO]
    recent_diagnoses: list[DiagnosisDTO]
    upcoming_appointments: list[AppointmentResponseDTO]
    last_appointment: Optional[AppointmentResponseDTO]
    disclaimer: str
