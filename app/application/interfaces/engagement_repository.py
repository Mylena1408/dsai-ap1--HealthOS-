from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from app.domain.entities.inbox import Audience, InboxNotification, InboxStatus, NotificationCategory, Sector
from app.domain.entities.system_alert import (
    AlertCandidate, AlertCategory, AlertLevel, SystemAlert, SystemAlertStatus,
)
from app.domain.events import DomainEvent, EventType


# ------------------------------------------------------------------- auditoria

@dataclass
class AuditFilters:
    event_types: list[EventType] = field(default_factory=list)
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    patient_id: Optional[uuid.UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


class AuditRepository(ABC):
    @abstractmethod
    async def add(self, event: DomainEvent) -> uuid.UUID: ...

    @abstractmethod
    async def search(self, filters: AuditFilters) -> tuple[list[tuple[uuid.UUID, DomainEvent]], int]: ...

    @abstractmethod
    async def count_by_type(self, date_from: Optional[datetime] = None) -> dict[str, int]: ...


# -------------------------------------------------------------- notificações

@dataclass
class InboxQuery:
    audience: Audience
    recipient_id: Optional[uuid.UUID] = None
    sector: Optional[Sector] = None
    statuses: list[InboxStatus] = field(default_factory=list)
    category: Optional[NotificationCategory] = None
    limit: int = 20
    offset: int = 0


class InboxRepository(ABC):
    @abstractmethod
    async def save(self, notification: InboxNotification) -> InboxNotification: ...

    @abstractmethod
    async def get(self, notification_id: uuid.UUID) -> Optional[InboxNotification]: ...

    @abstractmethod
    async def search(self, query: InboxQuery) -> tuple[list[InboxNotification], int]: ...

    @abstractmethod
    async def counts(self, query: InboxQuery) -> dict[InboxStatus, int]: ...

    @abstractmethod
    async def mark_all_read(self, query: InboxQuery, now: datetime) -> int: ...


# ------------------------------------------------------------------- alertas

@dataclass
class AlertFilters:
    statuses: list[SystemAlertStatus] = field(default_factory=list)
    categories: list[AlertCategory] = field(default_factory=list)
    levels: list[AlertLevel] = field(default_factory=list)
    patient_id: Optional[uuid.UUID] = None
    rule_code: Optional[str] = None
    limit: int = 50
    offset: int = 0


class SystemAlertRepository(ABC):
    @abstractmethod
    async def open_alerts(self) -> list[SystemAlert]: ...

    @abstractmethod
    async def save(self, alert: SystemAlert) -> SystemAlert: ...

    @abstractmethod
    async def get(self, alert_id: uuid.UUID) -> Optional[SystemAlert]: ...

    @abstractmethod
    async def search(self, filters: AlertFilters) -> tuple[list[SystemAlert], int]: ...

    @abstractmethod
    async def summary(self) -> dict[str, dict[str, int]]:
        """Contagem de alertas abertos por categoria e por nível."""


class AlertDetector(ABC):
    """Executa uma regra sobre os dados atuais e devolve as condições encontradas."""

    @abstractmethod
    async def detect(self, rule_code: str, now: datetime) -> list[AlertCandidate]: ...
