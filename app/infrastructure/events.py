"""Montagem do publicador de eventos com os manipuladores persistentes."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.event_handlers import AuditTrail, NotificationPolicy
from app.application.services.events import InProcessPublisher
from app.infrastructure.persistence.repositories.sqlalchemy_engagement_repository import (
    SQLAlchemyAuditRepository, SQLAlchemyInboxRepository,
)


def build_publisher(session: AsyncSession) -> InProcessPublisher:
    """Auditoria e notificações gravam na mesma sessão (mesma transação) da operação."""
    return InProcessPublisher([AuditTrail(SQLAlchemyAuditRepository(session)),
                               NotificationPolicy(SQLAlchemyInboxRepository(session))])
