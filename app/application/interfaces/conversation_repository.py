from abc import ABC, abstractmethod
from typing import Optional
import uuid

from app.domain.entities.assistant import Conversation, ConversationStatus


class ConversationRepository(ABC):

    @abstractmethod
    async def save(self, conversation: Conversation) -> Conversation:
        """Insere ou atualiza; mensagens são apenas acrescentadas."""

    @abstractmethod
    async def get(self, conversation_id: uuid.UUID) -> Optional[Conversation]: ...

    @abstractmethod
    async def search(self, patient_id: Optional[uuid.UUID], status: Optional[ConversationStatus],
                     limit: int, offset: int) -> tuple[list[Conversation], int]:
        """Conversas (sem mensagens), mais recentes primeiro."""
