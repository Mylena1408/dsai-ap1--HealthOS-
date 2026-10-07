"""Assistente educacional: funções de IA sobre o prontuário e chat com histórico."""
from datetime import datetime
from typing import Callable, Optional
import uuid

from app.application.dtos.assistant_dto import (
    AIResponseDTO, ChatMessageDTO, ConversationDTO, ExchangeDTO, FactDTO,
)
from app.application.dtos.common import Page
from app.application.interfaces.ai_service import AIService, AIUnavailableError
from app.application.interfaces.conversation_repository import ConversationRepository
from app.application.services.ai_context import PatientContextBuilder, describe_exam
from app.application.services.events import EventPublisher, NullPublisher
from app.domain.entities.assistant import (
    AIFeature, AIResponse, ChatMessage, Conversation, ConversationStatus,
)
from app.domain.entities.laboratory import ExamStatus
from app.domain.events import DomainEvent, EventType
from app.domain.exceptions.common import BusinessRuleViolation, EntityNotFoundError, ServiceUnavailableError
from app.domain.services.red_flags import URGENT_TEXT, has_red_flags

HISTORY_LIMIT = 20
# Modelo informado nas respostas dadas pela regra de segurança (sem chamar a IA).
SAFETY_MODEL = "regra-de-seguranca"


def _ai_dto(r: AIResponse) -> AIResponseDTO:
    return AIResponseDTO(feature=r.feature, text=r.text, provider=r.provider, model=r.model, suggestions=r.suggestions,
                         facts_used=[FactDTO(category=f.category, text=f.text) for f in r.facts_used],
                         urgent=r.urgent, disclaimer=r.disclaimer)


def _message_dto(m: ChatMessage) -> ChatMessageDTO:
    return ChatMessageDTO(id=m.id, role=m.role, content=m.content, created_at=m.created_at, provider=m.provider,
                          suggestions=m.suggestions, urgent=m.urgent,
                          facts_used=[FactDTO(category=f.category, text=f.text) for f in m.facts_used])


def _conversation_dto(c: Conversation) -> ConversationDTO:
    return ConversationDTO(id=c.id, title=c.title, patient_id=c.patient_id, status=c.status, created_at=c.created_at,
                           updated_at=c.updated_at, messages=[_message_dto(m) for m in c.messages])


class AssistantUseCase:

    def __init__(self, ai: AIService, contexts: PatientContextBuilder, conversations: ConversationRepository,
                 events: EventPublisher = NullPublisher(), clock: Callable[[], datetime] = datetime.now):
        self.ai = ai
        self.contexts = contexts
        self.conversations = conversations
        self.events = events
        self.clock = clock

    # ------------------------------------------------------------ funções de IA

    async def summarize(self, patient_id: uuid.UUID) -> AIResponseDTO:
        context = await self.contexts.build(patient_id)
        return await self._run(AIFeature.RECORD_SUMMARY, patient_id, self.ai.summarize_record(context))

    async def insights(self, patient_id: uuid.UUID) -> AIResponseDTO:
        context = await self.contexts.build(patient_id)
        return await self._run(AIFeature.INSIGHTS, patient_id, self.ai.generate_insights(context))

    async def analyze_exam(self, exam_id: uuid.UUID) -> AIResponseDTO:
        exam = await self.contexts.exam(exam_id)
        if exam.status != ExamStatus.RELEASED:
            raise BusinessRuleViolation("Somente resultados liberados podem ser explicados.")
        context = await self.contexts.build(exam.patient_id)
        description = f"{exam.exam_name}\n{describe_exam(exam)}"
        return await self._run(AIFeature.EXAM_ANALYSIS, exam.patient_id, self.ai.analyze_exam(context, description))

    async def symptoms(self, description: str, patient_id: Optional[uuid.UUID]) -> AIResponseDTO:
        context = await self.contexts.build(patient_id) if patient_id else None
        if has_red_flags(description):
            return await self._run(AIFeature.SYMPTOMS, patient_id, self._urgent(AIFeature.SYMPTOMS))
        return await self._run(AIFeature.SYMPTOMS, patient_id, self.ai.analyze_symptoms(description, context))

    # ------------------------------------------------------------------- chat

    async def start_conversation(self, patient_id: Optional[uuid.UUID], title: Optional[str]) -> ConversationDTO:
        if patient_id:
            await self.contexts.build(patient_id)  # valida o paciente (404 se não existir)
        conversation = Conversation(title=title or "Nova conversa", patient_id=patient_id, created_at=self.clock(),
                                    updated_at=self.clock())
        return _conversation_dto(await self.conversations.save(conversation))

    async def conversations_page(self, patient_id: Optional[uuid.UUID], status: Optional[ConversationStatus],
                                 limit: int, offset: int) -> Page[ConversationDTO]:
        items, total = await self.conversations.search(patient_id, status, limit, offset)
        return Page(items=[_conversation_dto(c) for c in items], total=total, limit=limit, offset=offset)

    async def get_conversation(self, conversation_id: uuid.UUID) -> ConversationDTO:
        return _conversation_dto(await self._conversation(conversation_id))

    async def send_message(self, conversation_id: uuid.UUID, content: str) -> ExchangeDTO:
        conversation = await self._conversation(conversation_id)
        history = conversation.recent_history(HISTORY_LIMIT)
        user_message = conversation.add_user_message(content, self.clock())
        if has_red_flags(user_message.content):
            response = await self._urgent(AIFeature.CHAT)
        else:
            context = await self.contexts.build(conversation.patient_id) if conversation.patient_id else None
            response = await self._call(self.ai.answer_question(user_message.content, context, history + [user_message]))
        assistant_message = conversation.add_assistant_message(response, self.clock())
        await self.conversations.save(conversation)
        await self._audit(AIFeature.CHAT, conversation.patient_id, conversation.id, response)
        return ExchangeDTO(user_message=_message_dto(user_message), assistant_message=_message_dto(assistant_message),
                           disclaimer=response.disclaimer)

    async def archive(self, conversation_id: uuid.UUID) -> ConversationDTO:
        conversation = await self._conversation(conversation_id)
        conversation.archive(self.clock())
        return _conversation_dto(await self.conversations.save(conversation))

    # ------------------------------------------------------------------ apoio

    async def _conversation(self, conversation_id: uuid.UUID) -> Conversation:
        conversation = await self.conversations.get(conversation_id)
        if not conversation:
            raise EntityNotFoundError("Conversa", conversation_id)
        return conversation

    async def _urgent(self, feature: AIFeature) -> AIResponse:
        """Regra de segurança: sinais de alerta recebem a orientação de urgência sem chamar a IA,
        qualquer que seja o provedor (nenhum dado do paciente sai do sistema)."""
        return AIResponse(text=URGENT_TEXT, provider=self.ai.provider, model=SAFETY_MODEL, feature=feature, urgent=True)

    @staticmethod
    async def _call(awaitable) -> AIResponse:
        try:
            return await awaitable
        except AIUnavailableError as exc:
            raise ServiceUnavailableError(str(exc)) from exc

    async def _run(self, feature: AIFeature, patient_id: Optional[uuid.UUID], awaitable) -> AIResponseDTO:
        response = await self._call(awaitable)
        # Sem paciente (ex.: sintomas avulsos), a auditoria usa um id fixo por função do assistente.
        await self._audit(feature, patient_id, patient_id or uuid.uuid5(uuid.NAMESPACE_URL, feature.value), response)
        return _ai_dto(response)

    async def _audit(self, feature: AIFeature, patient_id, entity_id: uuid.UUID, response: AIResponse) -> None:
        # Registra o USO da IA (função, provedor, urgência), nunca o conteúdo trocado.
        await self.events.publish(DomainEvent(
            event_type=EventType.AI_CONSULTED, occurred_at=self.clock(), entity_type="Assistente", entity_id=entity_id,
            patient_id=patient_id, summary=f"Assistente consultado: {feature.value} ({response.provider})"
                                           + (" — sinais de alerta orientados" if response.urgent else "") + ".",
            data={"feature": feature.value, "provider": response.provider, "model": response.model,
                  "urgent": response.urgent}))
