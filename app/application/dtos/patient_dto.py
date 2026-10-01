from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
import uuid
from datetime import date

class PatientCreateDTO(BaseModel):
    """DTO para a criação de um novo paciente."""
    full_name: str = Field(..., min_length=3, max_length=255)
    birth_date: date
    cpf: str = Field(..., description="CPF do paciente (aceita apenas números ou formato 000.000.000-00)")
    gender: str = Field(..., max_length=20)
    insurance_provider: Optional[str] = None
    insurance_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None

class PatientUpdateDTO(BaseModel):
    """DTO para atualização de dados do paciente."""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_number: Optional[str] = None

class PatientResponseDTO(BaseModel):
    """DTO para retorno de dados do paciente."""
    id: uuid.UUID
    full_name: str
    birth_date: date
    cpf: str
    gender: str
    insurance_provider: Optional[str]
    insurance_number: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
