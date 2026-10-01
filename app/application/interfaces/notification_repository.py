from abc import ABC, abstractmethod
from typing import List, Optional
import uuid
from app.domain.entities.notification import Notification

class NotificationRepository(ABC):
    """
    Interface de Repositório para Notificações.
    """

    @abstractmethod
    async def save(self, notification: Notification) -> Notification:
        pass

    @abstractmethod
    async def get_unread_by_user(self, user_id: uuid.UUID) -> List[Notification]:
        pass

    @abstractmethod
    async def get_unread_by_patient(self, patient_id: uuid.UUID) -> List[Notification]:
        pass

    @abstractmethod
    async def update_status(self, notification_id: uuid.UUID, status: str) -> bool:
        pass

    @abstractmethod
    async def mark_as_read(self, notification_id: uuid.UUID) -> bool:
        pass
