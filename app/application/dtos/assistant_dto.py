from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field

from app.domain.entities.assistant import MAX_MESSAGE_LENGTH, AIFeature, ConversationStatus, MessageRole


class FactDTO(BaseModel):
    category: str
    text: str


class AIResponseDTO(BaseModel):
    feature: AIFeature
    text: str
    provider: str
    model: str
    suggestions: list[str]
    facts_used: list[FactDTO]
    urgent: bool
    disclaimer: str


class SymptomsRequestDTO(BaseModel):
    description: str = Field(..., min_length=3, max_length=MAX_MESSAGE_LENGTH)
    patient_id: Optional[uuid.UUID] = None


class AIStatusDTO(BaseModel):
    provider: str
    model: str
    demo_mode: bool
    disclaimer: str


class ConversationCreateDTO(BaseModel):
    patient_id: Optional[uuid.UUID] = None
    title: Optional[str] = Field(None, max_length=120)


class MessageCreateDTO(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)


class ChatMessageDTO(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime
    provider: Optional[str]
    suggestions: list[str]
    facts_used: list[FactDTO]
    urgent: bool


class ConversationDTO(BaseModel):
    id: uuid.UUID
    title: str
    patient_id: Optional[uuid.UUID]
    status: ConversationStatus
    created_at: datetime
    updated_at: Optional[datetime]
    messages: list[ChatMessageDTO]


class ExchangeDTO(BaseModel):
    """Resultado de enviar uma mensagem: a pergunta registrada e a resposta do assistente."""
    user_message: ChatMessageDTO
    assistant_message: ChatMessageDTO
    disclaimer: str
