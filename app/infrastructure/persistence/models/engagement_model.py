"""Auditoria didática, caixa de notificações e alertas por regra (tabelas novas).

'audit_logs' e 'notifications' (legado) não são usadas nem alteradas por este módulo.
"""
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import JSON, Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.user_model import Base


class AuditEventModel(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_entity", "entity_type", "entity_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    # Sem chaves estrangeiras de propósito: o registro de auditoria sobrevive ao dado que descreve.
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(index=True)
    professional_id: Mapped[Optional[uuid.UUID]] = mapped_column()
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(JSON)


class InboxNotificationModel(Base):
    __tablename__ = "inbox_notifications"
    __table_args__ = (
        Index("ix_inbox_recipient", "audience", "recipient_id", "status"),
        Index("ix_inbox_sector", "audience", "sector", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    audience: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient_id: Mapped[Optional[uuid.UUID]] = mapped_column()
    sector: Mapped[Optional[str]] = mapped_column(String(30))
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="NORMAL")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(200))
    source_event: Mapped[Optional[str]] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="NAO_LIDA")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class SystemAlertModel(Base):
    __tablename__ = "system_alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    dedup_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(15), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[Optional[uuid.UUID]] = mapped_column()
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(index=True)
    link: Mapped[Optional[str]] = mapped_column(String(200))
    first_detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(120))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolution_note: Mapped[Optional[str]] = mapped_column(String(500))
    auto_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
