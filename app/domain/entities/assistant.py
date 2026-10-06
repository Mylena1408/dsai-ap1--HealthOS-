"""Assistente didático: contexto do paciente, respostas da IA e conversas.

A IA aqui é educacional: organiza e explica dados FICTÍCIOS do prontuário e nunca
emite diagnóstico. Toda resposta carrega o aviso padrão.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from app.domain.exceptions.common import BusinessRuleViolation, InvalidTransitionError

AI_DISCLAIMER = ("As informações apresentadas são educacionais e não substituem avaliação profissional. "
                 "Dados fictícios; nenhum diagnóstico é emitido.")
MAX_MESSAGE_LENGTH = 2000


class AIFeature(Enum):
    RECORD_SUMMARY = "RESUMO_PRONTUARIO"
    EXAM_ANALYSIS = "ANALISE_EXAME"
    SYMPTOMS = "ORIENTACAO_SINTOMAS"
    INSIGHTS = "OBSERVACOES"
    CHAT = "CHAT"


@dataclass(frozen=True)
class ContextFact:
    """Um fato do prontuário usado pela IA (exibido ao usuário para transparência)."""
    category: str   # ex.: "Alergia", "Exame", "Sinal vital"
    text: str


@dataclass
class PatientContext:
    """Contexto mínimo do paciente fictício. Não inclui CPF, e-mail, telefone nem endereço."""
    patient_id: uuid.UUID
    first_name: str
    age: int
    facts: list[ContextFact] = field(default_factory=list)

    def by_category(self, category: str) -> list[ContextFact]:
        return [f for f in self.facts if f.category == category]

    def as_text(self) -> str:
        lines = [f"Paciente fictício: {self.first_name}, {self.age} anos."]
        lines += [f"- [{f.category}] {f.text}" for f in self.facts]
        return "\n".join(lines)


@dataclass
class AIResponse:
    text: str
    provider: str
    model: str
    feature: AIFeature
    suggestions: list[str] = field(default_factory=list)
    facts_used: list[ContextFact] = field(default_factory=list)
    urgent: bool = False            # sinais de alerta: orientar atendimento imediato
    disclaimer: str = AI_DISCLAIMER


# ---------------------------------------------------------------------- chat

class ConversationStatus(Enum):
    ACTIVE = "ATIVA"
    ARCHIVED = "ARQUIVADA"


class MessageRole(Enum):
    USER = "USUARIO"
    ASSISTANT = "ASSISTENTE"


@dataclass
class ChatMessage:
    role: MessageRole
    content: str
    created_at: datetime
    provider: Optional[str] = None
    suggestions: list[str] = field(default_factory=list)
    facts_used: list[ContextFact] = field(default_factory=list)
    urgent: bool = False
    id: Optional[uuid.UUID] = None


@dataclass
class Conversation:
    title: str
    created_at: datetime
    patient_id: Optional[uuid.UUID] = None
    status: ConversationStatus = ConversationStatus.ACTIVE
    messages: list[ChatMessage] = field(default_factory=list)
    updated_at: Optional[datetime] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        self.title = (self.title or "").strip()[:120] or "Nova conversa"

    def add_user_message(self, content: str, now: datetime) -> ChatMessage:
        if self.status != ConversationStatus.ACTIVE:
            raise InvalidTransitionError("Conversa", self.status.value, "NOVA_MENSAGEM")
        text = (content or "").strip()
        if not text:
            raise BusinessRuleViolation("A mensagem não pode ser vazia.")
        if len(text) > MAX_MESSAGE_LENGTH:
            raise BusinessRuleViolation(f"A mensagem deve ter no máximo {MAX_MESSAGE_LENGTH} caracteres.")
        message = ChatMessage(role=MessageRole.USER, content=text, created_at=now)
        self.messages.append(message)
        self.updated_at = now
        if self.title == "Nova conversa":
            self.title = text[:60]
        return message

    def add_assistant_message(self, response: AIResponse, now: datetime) -> ChatMessage:
        message = ChatMessage(role=MessageRole.ASSISTANT, content=response.text, created_at=now,
                              provider=f"{response.provider}:{response.model}", suggestions=response.suggestions,
                              facts_used=response.facts_used, urgent=response.urgent)
        self.messages.append(message)
        self.updated_at = now
        return message

    def recent_history(self, limit: int) -> list[ChatMessage]:
        """Últimas mensagens para dar continuidade (o provedor recebe no máximo `limit`)."""
        return self.messages[-limit:]

    def archive(self, now: datetime) -> None:
        if self.status == ConversationStatus.ARCHIVED:
            raise InvalidTransitionError("Conversa", self.status.value, ConversationStatus.ARCHIVED.value)
        self.status, self.updated_at = ConversationStatus.ARCHIVED, now
