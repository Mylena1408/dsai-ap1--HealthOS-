"""Assistente educacional (IA desacoplada) e chat com histórico."""
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.assistant_dto import (
    AIResponseDTO, AIStatusDTO, ConversationCreateDTO, ConversationDTO, ExchangeDTO, MessageCreateDTO,
    SymptomsRequestDTO,
)
from app.application.dtos.common import Page
from app.application.services.ai_context import ContextSources, PatientContextBuilder
from app.application.use_cases.assistant_use_case import AssistantUseCase
from app.domain.entities.assistant import AI_DISCLAIMER, ConversationStatus
from app.infrastructure.ai.factory import get_ai_service
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.sqlalchemy_conversation_repository import (
    SQLAlchemyConversationRepository,
)
from app.presentation.api.dependencies import get_events
from app.presentation.api.v1.clinical_monitoring.router import get_lab, get_vitals
from app.presentation.api.v1.dashboards.router import get_dashboards
from app.presentation.api.v1.medical_records.router import get_use_case as get_records
from app.presentation.api.v1.pharmacy_v2.router import get_prescriptions

router = APIRouter(tags=["Assistente (IA educacional)"])


async def get_assistant(session: AsyncSession = Depends(get_db), events=Depends(get_events),
                        records=Depends(get_records), vitals=Depends(get_vitals), laboratory=Depends(get_lab),
                        prescriptions=Depends(get_prescriptions), dashboards=Depends(get_dashboards),
                        ai=Depends(get_ai_service)) -> AssistantUseCase:
    contexts = PatientContextBuilder(ContextSources(records=records, vitals=vitals, laboratory=laboratory,
                                                    prescriptions=prescriptions, dashboards=dashboards))
    return AssistantUseCase(ai, contexts, SQLAlchemyConversationRepository(session), events)


Assistant = Depends(get_assistant)


@router.get("/ai/status", response_model=AIStatusDTO, summary="Provedor de IA configurado (demo ou real)")
async def ai_status(ai=Depends(get_ai_service)):
    return AIStatusDTO(provider=ai.provider, model=ai.model, demo_mode=ai.provider == "demo", disclaimer=AI_DISCLAIMER)


@router.post("/ai/patients/{patient_id}/summary", response_model=AIResponseDTO)
async def summarize_record(patient_id: uuid.UUID, assistant: AssistantUseCase = Assistant):
    return await assistant.summarize(patient_id)


@router.post("/ai/patients/{patient_id}/insights", response_model=AIResponseDTO)
async def insights(patient_id: uuid.UUID, assistant: AssistantUseCase = Assistant):
    return await assistant.insights(patient_id)


@router.post("/ai/exams/{exam_id}/analysis", response_model=AIResponseDTO,
             summary="Explicação educacional de um resultado liberado")
async def analyze_exam(exam_id: uuid.UUID, assistant: AssistantUseCase = Assistant):
    return await assistant.analyze_exam(exam_id)


@router.post("/ai/symptoms", response_model=AIResponseDTO,
             summary="Organiza sintomas para a consulta e orienta sinais de alerta (sem diagnóstico)")
async def symptoms(request: SymptomsRequestDTO, assistant: AssistantUseCase = Assistant):
    return await assistant.symptoms(request.description, request.patient_id)


@router.post("/conversations", response_model=ConversationDTO, status_code=status.HTTP_201_CREATED)
async def start_conversation(request: ConversationCreateDTO, assistant: AssistantUseCase = Assistant):
    return await assistant.start_conversation(request.patient_id, request.title)


@router.get("/conversations", response_model=Page[ConversationDTO])
async def list_conversations(patient_id: Optional[uuid.UUID] = None,
                             status_: Optional[ConversationStatus] = Query(None, alias="status"),
                             limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                             assistant: AssistantUseCase = Assistant):
    return await assistant.conversations_page(patient_id, status_, limit, offset)


@router.get("/conversations/{conversation_id}", response_model=ConversationDTO)
async def get_conversation(conversation_id: uuid.UUID, assistant: AssistantUseCase = Assistant):
    return await assistant.get_conversation(conversation_id)


@router.post("/conversations/{conversation_id}/messages", response_model=ExchangeDTO,
             status_code=status.HTTP_201_CREATED)
async def send_message(conversation_id: uuid.UUID, request: MessageCreateDTO, assistant: AssistantUseCase = Assistant):
    return await assistant.send_message(conversation_id, request.content)


@router.post("/conversations/{conversation_id}/archive", response_model=ConversationDTO)
async def archive_conversation(conversation_id: uuid.UUID, assistant: AssistantUseCase = Assistant):
    return await assistant.archive(conversation_id)
