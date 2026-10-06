"""Histórico de atividades de um profissional (consultas, sinais vitais, prescrições, dispensações, exames)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class ActivityKind(Enum):
    APPOINTMENT = "CONSULTA"
    VITAL_SIGNS = "SINAIS_VITAIS"
    PRESCRIPTION = "PRESCRICAO"
    DISPENSATION = "DISPENSACAO"
    EXAM_REQUESTED = "EXAME_SOLICITADO"
    EXAM_VALIDATED = "EXAME_VALIDADO"


@dataclass(frozen=True)
class ActivityItem:
    kind: ActivityKind
    occurred_at: datetime
    description: str
    patient_id: Optional[uuid.UUID]
    patient_name: Optional[str]


class ProfessionalActivityQueries(ABC):
    @abstractmethod
    async def totals(self, professional_id: uuid.UUID, until: datetime) -> dict[ActivityKind, int]:
        """Quantidade de registros de cada tipo feitos pelo profissional até `until`."""

    @abstractmethod
    async def recent(self, professional_id: uuid.UUID, until: datetime, limit: int) -> list[ActivityItem]:
        """Registros até `until` (o que já aconteceu), do mais novo para o mais antigo."""
