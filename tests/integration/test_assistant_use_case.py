import pytest
from sqlalchemy import func, select

from app.application.interfaces.ai_service import AIUnavailableError
from app.application.services.ai_context import ContextSources, PatientContextBuilder
from app.application.services.events import InProcessPublisher
from app.application.use_cases.assistant_use_case import AssistantUseCase
from app.application.use_cases.medical_record_use_case import MedicalRecordUseCase
from app.domain.entities.assistant import MessageRole
from app.domain.entities.laboratory import ExamStatus
from app.domain.events import EventType
from app.domain.exceptions.common import BusinessRuleViolation, ServiceUnavailableError
from app.infrastructure.ai.demo_provider import DemoAIService
from app.infrastructure.persistence.models.assistant_model import ConversationMessageModel
from app.infrastructure.persistence.models.clinical_monitoring_model import ExamRequestModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.persistence.repositories.sqlalchemy_conversation_repository import (
    SQLAlchemyConversationRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_medical_record_repository import (
    SQLAlchemyMedicalRecordRepository, SQLAlchemyPatientDirectoryRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_timeline_repository import SQLAlchemyTimelineRepository


class FailingAI(DemoAIService):
    async def answer_question(self, question, context, history):
        raise AIUnavailableError("Provedor fora do ar (simulado).")


@pytest.fixture
async def assistant(seeded):
    s = seeded["session"]
    deps = seeded["use_case"].d
    records = MedicalRecordUseCase(
        SQLAlchemyMedicalRecordRepository(s), SQLAlchemyPatientDirectoryRepository(s), SQLAlchemyTimelineRepository(s),
        SQLAlchemyAppointmentRepository(s), deps.professional_repo, deps.appointments)
    contexts = PatientContextBuilder(ContextSources(records=records, vitals=deps.vitals, laboratory=deps.laboratory,
                                                    prescriptions=deps.prescriptions, dashboards=seeded["use_case"]))
    events = InProcessPublisher()
    return dict(session=s, contexts=contexts, events=events,
                use_case=AssistantUseCase(DemoAIService(), contexts, SQLAlchemyConversationRepository(s), events))


async def a_patient_with_exams(session):
    return (await session.scalars(select(ExamRequestModel.patient_id).where(
        ExamRequestModel.status == ExamStatus.RELEASED.value))).first()


async def test_context_is_minimal_and_has_no_identifiers(assistant):
    session = assistant["session"]
    patient = await session.get(PatientModel, await a_patient_with_exams(session))
    context = await assistant["contexts"].build(patient.id)
    text = context.as_text()
    assert context.first_name == patient.full_name.split()[0]
    for identifier in (patient.cpf, patient.email, patient.phone, patient.address):
        if identifier:
            assert identifier not in text
    assert any(f.category == "Exame" for f in context.facts)


async def test_ai_features_over_real_data(assistant):
    session, uc = assistant["session"], assistant["use_case"]
    patient_id = await a_patient_with_exams(session)
    summary = await uc.summarize(patient_id)
    assert summary.text.startswith("Resumo organizado do prontuário") and summary.facts_used

    exam_id = (await session.scalars(select(ExamRequestModel.id).where(
        ExamRequestModel.patient_id == patient_id, ExamRequestModel.status == ExamStatus.RELEASED.value))).first()
    analysis = await uc.analyze_exam(exam_id)
    assert "Explicação educacional do exame" in analysis.text

    pending = (await session.scalars(select(ExamRequestModel.id).where(
        ExamRequestModel.status == ExamStatus.REQUESTED.value))).first()
    with pytest.raises(BusinessRuleViolation, match="liberados"):
        await uc.analyze_exam(pending)

    audited = [e for e in assistant["events"].published if e.event_type == EventType.AI_CONSULTED]
    assert [e.data["feature"] for e in audited] == ["RESUMO_PRONTUARIO", "ANALISE_EXAME"]
    assert all("Resumo organizado" not in e.summary for e in audited)  # só o uso, nunca o conteúdo


async def test_chat_flow_is_persisted(assistant):
    session, uc = assistant["session"], assistant["use_case"]
    patient_id = await a_patient_with_exams(session)
    conversation = await uc.start_conversation(patient_id, None)
    exchange = await uc.send_message(conversation.id, "Quais medicamentos estão em uso?")
    assert exchange.user_message.role == MessageRole.USER and exchange.assistant_message.role == MessageRole.ASSISTANT
    assert exchange.assistant_message.provider == "demo:regras-deterministicas"
    await uc.send_message(conversation.id, "E os exames?")

    stored = await uc.get_conversation(conversation.id)
    assert [m.role for m in stored.messages] == [MessageRole.USER, MessageRole.ASSISTANT] * 2
    assert stored.title == "Quais medicamentos estão em uso?"
    listed = await uc.conversations_page(patient_id, None, 10, 0)
    assert listed.total == 1 and listed.items[0].messages == []  # listagem não carrega mensagens

    archived = await uc.archive(conversation.id)
    assert archived.status.value == "ARQUIVADA"


async def test_provider_failure_becomes_503_and_saves_nothing(assistant):
    session = assistant["session"]
    failing = AssistantUseCase(FailingAI(), assistant["contexts"], SQLAlchemyConversationRepository(session))
    conversation = await failing.start_conversation(None, "Teste")
    before = await session.scalar(select(func.count()).select_from(ConversationMessageModel))
    with pytest.raises(ServiceUnavailableError):
        await failing.send_message(conversation.id, "Olá")
    after = await session.scalar(select(func.count()).select_from(ConversationMessageModel))
    assert after == before
