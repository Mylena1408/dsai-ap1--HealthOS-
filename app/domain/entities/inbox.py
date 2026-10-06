"""Caixa de notificações interna (sem envio real de e-mail/SMS).

    NAO_LIDA ⇄ LIDA ─► ARQUIVADA ─► (desarquivar) LIDA
       └──────────────► ARQUIVADA
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from app.domain.exceptions.common import BusinessRuleViolation, InvalidTransitionError


class Audience(Enum):
    PATIENT = "PACIENTE"
    PROFESSIONAL = "PROFISSIONAL"
    SECTOR = "SETOR"


class Sector(Enum):
    RECEPTION = "RECEPCAO"
    LABORATORY = "LABORATORIO"
    PHARMACY = "FARMACIA"
    CLINICAL_COORDINATION = "COORDENACAO_CLINICA"
    ADMINISTRATION = "ADMINISTRACAO"


class NotificationCategory(Enum):
    APPOINTMENT = "CONSULTA"
    EXAM = "EXAME"
    MEDICATION = "MEDICAMENTO"
    ALERT = "ALERTA"
    FINANCIAL = "FINANCEIRO"
    ADMINISTRATIVE = "ADMINISTRATIVO"


class InboxStatus(Enum):
    UNREAD = "NAO_LIDA"
    READ = "LIDA"
    ARCHIVED = "ARQUIVADA"


class Priority(Enum):
    NORMAL = "NORMAL"
    HIGH = "ALTA"


@dataclass
class InboxNotification:
    audience: Audience
    category: NotificationCategory
    title: str
    message: str
    created_at: datetime
    recipient_id: Optional[uuid.UUID] = None  # paciente ou profissional
    sector: Optional[Sector] = None
    priority: Priority = Priority.NORMAL
    link: Optional[str] = None                # caminho no portal, ex.: /app/laboratorio
    source_event: Optional[str] = None
    status: InboxStatus = InboxStatus.UNREAD
    read_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        if self.audience == Audience.SECTOR and self.sector is None:
            raise BusinessRuleViolation("Notificações para setor exigem o setor de destino.")
        if self.audience != Audience.SECTOR and self.recipient_id is None:
            raise BusinessRuleViolation("Notificações pessoais exigem o destinatário.")
        if not self.title.strip():
            raise BusinessRuleViolation("O título da notificação é obrigatório.")

    def mark_read(self, now: datetime) -> None:
        if self.status != InboxStatus.UNREAD:
            raise InvalidTransitionError("Notificação", self.status.value, InboxStatus.READ.value)
        self.status, self.read_at = InboxStatus.READ, now

    def mark_unread(self) -> None:
        if self.status != InboxStatus.READ:
            raise InvalidTransitionError("Notificação", self.status.value, InboxStatus.UNREAD.value)
        self.status, self.read_at = InboxStatus.UNREAD, None

    def archive(self, now: datetime) -> None:
        if self.status == InboxStatus.ARCHIVED:
            raise InvalidTransitionError("Notificação", self.status.value, InboxStatus.ARCHIVED.value)
        self.read_at = self.read_at or now  # arquivar implica ter visto
        self.status, self.archived_at = InboxStatus.ARCHIVED, now

    def unarchive(self) -> None:
        if self.status != InboxStatus.ARCHIVED:
            raise InvalidTransitionError("Notificação", self.status.value, InboxStatus.READ.value)
        self.status, self.archived_at = InboxStatus.READ, None
