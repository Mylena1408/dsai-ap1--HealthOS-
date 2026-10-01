from typing import List, Optional
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.domain.entities.notification import Notification, NotificationType, NotificationChannel, NotificationStatus
from app.application.interfaces.notification_repository import NotificationRepository
from app.infrastructure.persistence.models.notification_model import NotificationModel

class SQLAlchemyNotificationRepository(NotificationRepository):
    """
    Implementação do NotificationRepository utilizando SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, notification: Notification) -> Notification:
        db_notification = NotificationModel(
            id=notification.id or uuid.uuid4(),
            user_id=notification.user_id,
            patient_id=notification.patient_id,
            type=notification.type.value,
            channel=notification.channel.value,
            title=notification.title,
            message=notification.message,
            priority=notification.priority,
            status=notification.status.value,
            metadata_json=notification.metadata,
            sent_at=notification.sent_at,
            read_at=notification.read_at
        )
        self.session.add(db_notification)
        await self.session.flush()
        notification.id = db_notification.id
        return notification

    async def get_unread_by_user(self, user_id: uuid.UUID) -> List[Notification]:
        stmt = select(NotificationModel).where(
            NotificationModel.user_id == user_id,
            NotificationModel.status != "READ"
        )
        result = await self.session.execute(stmt)
        return [self._map_to_domain(n) for n in result.scalars().all()]

    async def get_unread_by_patient(self, patient_id: uuid.UUID) -> List[Notification]:
        stmt = select(NotificationModel).where(
            NotificationModel.patient_id == patient_id,
            NotificationModel.status != "READ"
        )
        result = await self.session.execute(stmt)
        return [self._map_to_domain(n) for n in result.scalars().all()]

    async def update_status(self, notification_id: uuid.UUID, status_value: str) -> bool:
        db_notification = await self.session.get(NotificationModel, notification_id)
        if not db_notification:
            return False

        db_notification.status = status_value
        await self.session.flush()
        return True

    async def mark_as_read(self, notification_id: uuid.UUID) -> bool:
        db_notification = await self.session.get(NotificationModel, notification_id)
        if not db_notification:
            return False

        db_notification.status = "READ"
        db_notification.read_at = datetime.now()
        await self.session.flush()
        return True

    def _map_to_domain(self, db_model: NotificationModel) -> Notification:
        return Notification(
            id=db_model.id,
            user_id=db_model.user_id,
            patient_id=db_model.patient_id,
            type=NotificationType(db_model.type),
            channel=NotificationChannel(db_model.channel),
            title=db_model.title,
            message=db_model.message,
            priority=db_model.priority,
            status=NotificationStatus(db_model.status),
            metadata=db_model.metadata_json or {},
            created_at=db_model.created_at,
            sent_at=db_model.sent_at,
            read_at=db_model.read_at
        )
