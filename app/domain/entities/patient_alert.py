from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import uuid
from enum import Enum

class AlertSeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class AlertType(Enum):
    ALLERGY = "ALLERGY"
    CHRONIC_CONDITION = "CHRONIC_CONDITION"
    RISK_FACTOR = "RISK_FACTOR"
    OTHER = "OTHER"

@dataclass
class PatientAlert:
    """
    Entidade de Domínio PatientAlert.
    Representa um alerta crítico associado a um paciente (ex: Alergia a Penicilina).
    """
    patient_id: uuid.UUID
    alert_type: AlertType
    severity: AlertSeverity
    description: str
    created_at: datetime
    is_active: bool = True
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        if not self.description or len(self.description) < 3:
            raise ValueError("A descrição do alerta deve ter pelo menos 3 caracteres.")

    def deactivate(self):
        """Desativa o alerta (ex: paciente superou a condição)."""
        self.is_active = False

    def activate(self):
        """Reativa um alerta previamente desativado."""
        self.is_active = True
