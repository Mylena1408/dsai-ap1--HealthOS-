from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
from app.domain.entities.patient_alert import AlertType, AlertSeverity

class PatientAlertCreateDTO(BaseModel):
    """DTO para a criação de um alerta de paciente."""
    patient_id: uuid.UUID
    alert_type: AlertType
    severity: AlertSeverity
    description: str = Field(..., min_length=3, max_length=500)

class PatientAlertUpdateDTO(BaseModel):
    """DTO para atualização de alertas."""
    description: Optional[str] = None
    is_active: Optional[bool] = None
    severity: Optional[AlertSeverity] = None

class PatientAlertResponseDTO(BaseModel):
    """DTO para resposta de alerta."""
    id: uuid.UUID
    patient_id: uuid.UUID
    alert_type: AlertType
    severity: AlertSeverity
    description: str
    is_active: bool
    created_at: datetime
