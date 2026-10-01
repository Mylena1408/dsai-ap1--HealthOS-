from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

class ClinicalNoteCreateDTO(BaseModel):
    """DTO para a criação de uma nota clínica."""
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    content: str = Field(..., min_length=10, max_length=10000)

class ClinicalNoteUpdateDTO(BaseModel):
    """DTO para a atualização de rascunhos de notas."""
    content: str = Field(..., min_length=10, max_length=10000)

class ClinicalNoteResponseDTO(BaseModel):
    """DTO para resposta de notas clínicas."""
    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    content: str
    timestamp: datetime
    status: str
    version: int
