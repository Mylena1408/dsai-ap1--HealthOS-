"""Alertas gerados por regras sobre os dados reais do sistema.

    ATIVO ─► RECONHECIDO ─► RESOLVIDO
      └───────────────────► RESOLVIDO

Resolução manual (com nota) ou automática, quando a regra deixa de detectar a condição.
Se a condição reaparecer depois de resolvida, um novo alerta é aberto.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from app.domain.exceptions.common import BusinessRuleViolation, InvalidTransitionError


class AlertCategory(Enum):
    CLINICAL = "CLINICO"
    LABORATORY = "LABORATORIAL"
    MEDICATION = "MEDICAMENTO"
    APPOINTMENT = "CONSULTA"
    STOCK = "ESTOQUE"
    ADMINISTRATIVE = "ADMINISTRATIVO"
    SYSTEM = "SISTEMA"


class AlertLevel(Enum):
    INFO = "INFO"
    WARNING = "ATENCAO"
    CRITICAL = "CRITICO"


class SystemAlertStatus(Enum):
    ACTIVE = "ATIVO"
    ACKNOWLEDGED = "RECONHECIDO"
    RESOLVED = "RESOLVIDO"


@dataclass(frozen=True)
class AlertCandidate:
    """O que uma regra detectou agora. `dedup_key` identifica a mesma condição entre execuções."""
    rule_code: str
    dedup_key: str
    category: AlertCategory
    level: AlertLevel
    title: str
    message: str
    subject_type: str
    subject_id: Optional[uuid.UUID] = None
    patient_id: Optional[uuid.UUID] = None
    link: Optional[str] = None


@dataclass
class SystemAlert:
    rule_code: str
    dedup_key: str
    category: AlertCategory
    level: AlertLevel
    title: str
    message: str
    subject_type: str
    first_detected_at: datetime
    last_detected_at: datetime
    subject_id: Optional[uuid.UUID] = None
    patient_id: Optional[uuid.UUID] = None
    link: Optional[str] = None
    status: SystemAlertStatus = SystemAlertStatus.ACTIVE
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    auto_resolved: bool = False
    id: Optional[uuid.UUID] = None

    @classmethod
    def open(cls, candidate: AlertCandidate, now: datetime) -> "SystemAlert":
        return cls(rule_code=candidate.rule_code, dedup_key=candidate.dedup_key, category=candidate.category,
                   level=candidate.level, title=candidate.title, message=candidate.message,
                   subject_type=candidate.subject_type, subject_id=candidate.subject_id,
                   patient_id=candidate.patient_id, link=candidate.link,
                   first_detected_at=now, last_detected_at=now)

    @property
    def is_open(self) -> bool:
        return self.status != SystemAlertStatus.RESOLVED

    def refresh(self, candidate: AlertCandidate, now: datetime) -> bool:
        """Atualiza com a detecção mais recente. Retorna True se o nível piorou."""
        escalated = (list(AlertLevel).index(candidate.level) > list(AlertLevel).index(self.level))
        self.level, self.title, self.message = candidate.level, candidate.title, candidate.message
        self.last_detected_at = now
        return escalated

    def acknowledge(self, by: str, now: datetime) -> None:
        if self.status != SystemAlertStatus.ACTIVE:
            raise InvalidTransitionError("Alerta", self.status.value, SystemAlertStatus.ACKNOWLEDGED.value)
        if not by or len(by.strip()) < 3:
            raise BusinessRuleViolation("Informe quem está reconhecendo o alerta.")
        self.status, self.acknowledged_at, self.acknowledged_by = SystemAlertStatus.ACKNOWLEDGED, now, by.strip()

    def resolve(self, now: datetime, note: Optional[str] = None, automatic: bool = False) -> None:
        if self.status == SystemAlertStatus.RESOLVED:
            raise InvalidTransitionError("Alerta", self.status.value, SystemAlertStatus.RESOLVED.value)
        if not automatic and (not note or len(note.strip()) < 5):
            raise BusinessRuleViolation("Descreva a resolução (mínimo de 5 caracteres).")
        self.status, self.resolved_at, self.auto_resolved = SystemAlertStatus.RESOLVED, now, automatic
        self.resolution_note = note.strip() if note else "Resolvido automaticamente: a condição deixou de ser detectada."
