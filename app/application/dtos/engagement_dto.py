from datetime import datetime
from typing import Any, Optional
import uuid

from pydantic import BaseModel, Field

from app.domain.entities.inbox import Audience, InboxStatus, NotificationCategory, Priority, Sector
from app.domain.entities.system_alert import AlertCategory, AlertLevel, SystemAlertStatus
from app.domain.events import EventType


class AuditEventDTO(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    event_type: EventType
    entity_type: str
    entity_id: uuid.UUID
    patient_id: Optional[uuid.UUID]
    professional_id: Optional[uuid.UUID]
    summary: str
    data: dict[str, Any]


class InboxNotificationDTO(BaseModel):
    id: uuid.UUID
    audience: Audience
    recipient_id: Optional[uuid.UUID]
    sector: Optional[Sector]
    category: NotificationCategory
    priority: Priority
    title: str
    message: str
    link: Optional[str]
    source_event: Optional[str]
    status: InboxStatus
    created_at: datetime
    read_at: Optional[datetime]
    archived_at: Optional[datetime]


class InboxCountsDTO(BaseModel):
    unread: int
    read: int
    archived: int


class SystemAlertDTO(BaseModel):
    id: uuid.UUID
    rule_code: str
    category: AlertCategory
    level: AlertLevel
    status: SystemAlertStatus
    title: str
    message: str
    subject_type: str
    subject_id: Optional[uuid.UUID]
    patient_id: Optional[uuid.UUID]
    link: Optional[str]
    first_detected_at: datetime
    last_detected_at: datetime
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    resolved_at: Optional[datetime]
    resolution_note: Optional[str]
    auto_resolved: bool


class AcknowledgeDTO(BaseModel):
    by: str = Field(..., min_length=3, max_length=120, description="Nome de quem reconhece (perfil de demonstração)")


class ResolveDTO(BaseModel):
    note: str = Field(..., min_length=5, max_length=500)


class EvaluateDTO(BaseModel):
    rules: Optional[list[str]] = Field(None, description="Padrão: todas as regras")


class EvaluationReportDTO(BaseModel):
    evaluated_at: datetime
    opened: int
    refreshed: int
    escalated: int
    auto_resolved: int
    by_rule: dict[str, int]


class AlertRuleDTO(BaseModel):
    code: str
    category: AlertCategory
    description: str
    sector: Sector
