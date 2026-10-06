from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class TimelineEventType(Enum):
    REGISTRATION = "CADASTRO"
    APPOINTMENT = "CONSULTA"
    CLINICAL_NOTE = "NOTA_CLINICA"
    ALERT = "ALERTA"
    TRIAGE = "TRIAGEM"
    ALLERGY = "ALERGIA"
    CONDITION = "CONDICAO"
    DIAGNOSIS = "DIAGNOSTICO"
    PROCEDURE = "PROCEDIMENTO"
    VITAL_SIGNS = "SINAIS_VITAIS"
    EXAM = "EXAME"


@dataclass(frozen=True)
class TimelineEvent:
    """Evento somente-leitura da linha do tempo, derivado dos registros de cada módulo."""
    occurred_at: datetime
    event_type: TimelineEventType
    title: str
    source_id: uuid.UUID
    description: Optional[str] = None
    status: Optional[str] = None
