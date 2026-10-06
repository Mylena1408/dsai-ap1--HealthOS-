import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from app.application.interfaces.conversation_repository import ConversationRepository
from app.domain.entities.assistant import (
    ChatMessage, ContextFact, Conversation, ConversationStatus, MessageRole,
)
from app.infrastructure.persistence.models.assistant_model import ConversationMessageModel, ConversationModel


class SQLAlchemyConversationRepository(ConversationRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, conversation):
        model = await self.session.get(ConversationModel, conversation.id) if conversation.id else None
        if model is None:
            model = ConversationModel(id=conversation.id or uuid.uuid4(), messages=[])
            self.session.add(model)
        model.patient_id, model.title = conversation.patient_id, conversation.title
        model.status = conversation.status.value
        model.created_at, model.updated_at = conversation.created_at, conversation.updated_at
        for message in conversation.messages:
            if message.id is None:  # somente acréscimo
                message.id = uuid.uuid4()
                model.messages.append(ConversationMessageModel(
                    id=message.id, role=message.role.value, content=message.content, provider=message.provider,
                    suggestions=list(message.suggestions),
                    facts_used=[{"category": f.category, "text": f.text} for f in message.facts_used],
                    urgent=message.urgent, created_at=message.created_at))
        await self.session.flush()
        conversation.id = model.id
        return conversation

    async def get(self, conversation_id):
        model = await self.session.get(ConversationModel, conversation_id)
        return self._to_domain(model, with_messages=True) if model else None

    async def search(self, patient_id, status, limit, offset):
        conditions = []
        if patient_id:
            conditions.append(ConversationModel.patient_id == patient_id)
        if status:
            conditions.append(ConversationModel.status == status.value)
        total = await self.session.scalar(select(func.count()).select_from(ConversationModel).where(*conditions))
        rows = await self.session.scalars(
            select(ConversationModel).options(noload(ConversationModel.messages)).where(*conditions)
            .order_by(desc(ConversationModel.updated_at)).limit(limit).offset(offset))
        return [self._to_domain(m, with_messages=False) for m in rows], total

    @staticmethod
    def _to_domain(m: ConversationModel, with_messages: bool) -> Conversation:
        messages = [ChatMessage(
            id=x.id, role=MessageRole(x.role), content=x.content, created_at=x.created_at, provider=x.provider,
            suggestions=x.suggestions or [], urgent=x.urgent,
            facts_used=[ContextFact(f["category"], f["text"]) for f in (x.facts_used or [])],
        ) for x in m.messages] if with_messages else []
        return Conversation(id=m.id, title=m.title, patient_id=m.patient_id, status=ConversationStatus(m.status),
                            created_at=m.created_at, updated_at=m.updated_at, messages=messages)
