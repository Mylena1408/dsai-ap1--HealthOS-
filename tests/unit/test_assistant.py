from datetime import datetime
from types import SimpleNamespace
import uuid

import pytest

from app.application.interfaces.ai_service import AIUnavailableError
from app.domain.entities.assistant import (
    AI_DISCLAIMER, AIFeature, AIResponse, ContextFact, Conversation, ConversationStatus, MessageRole, PatientContext,
)
from app.domain.exceptions.common import BusinessRuleViolation, InvalidTransitionError
from app.infrastructure.ai.claude_provider import DEFAULT_MODEL, ClaudeAIService
from app.infrastructure.ai.demo_provider import DemoAIService

NOW = datetime(2026, 10, 6, 10, 0)
CONTEXT = PatientContext(patient_id=uuid.uuid4(), first_name="Maria", age=46, facts=[
    ContextFact("Alergia", "Penicilina (grave): urticária"),
    ContextFact("Medicamento", "Losartana Demo 50mg — 1 comprimido, 1 vez ao dia"),
    ContextFact("Exame", "Perfil lipídico em 01/10/2026: fora da referência — Colesterol LDL 160 mg/dL (alto)"),
    ContextFact("Sinal vital", "Pressão sistólica: 150 mmHg em 05/10/2026 — alterado"),
    ContextFact("Condição", "Hipertensão arterial — ativa"),
    ContextFact("Consulta", "Última consulta: 01/09/2026 com Dr. João"),
])


# ----------------------------------------------------------------- conversa

def test_conversation_rules():
    conversation = Conversation(title="", created_at=NOW)
    assert conversation.title == "Nova conversa"
    conversation.add_user_message("  Quais exames estão alterados?  ", NOW)
    assert conversation.title == "Quais exames estão alterados?"  # título vem da 1ª pergunta
    with pytest.raises(BusinessRuleViolation):
        conversation.add_user_message("   ", NOW)
    with pytest.raises(BusinessRuleViolation):
        conversation.add_user_message("x" * 2001, NOW)

    reply = AIResponse(text="Resposta", provider="demo", model="m", feature=AIFeature.CHAT, suggestions=["a"])
    conversation.add_assistant_message(reply, NOW)
    assert [m.role for m in conversation.messages] == [MessageRole.USER, MessageRole.ASSISTANT]
    assert conversation.recent_history(1)[0].role == MessageRole.ASSISTANT

    conversation.archive(NOW)
    assert conversation.status == ConversationStatus.ARCHIVED
    with pytest.raises(InvalidTransitionError):
        conversation.add_user_message("depois de arquivar", NOW)


# --------------------------------------------------------------- IA demo

async def test_demo_summary_lists_every_category_and_is_deterministic():
    ai = DemoAIService()
    first, second = await ai.summarize_record(CONTEXT), await ai.summarize_record(CONTEXT)
    assert first.text == second.text
    for section in ("Alergias:", "Condições:", "Medicamentos em uso:", "Exames:", "Sinais vitais:", "Consultas:"):
        assert section in first.text
    assert first.disclaimer == AI_DISCLAIMER and first.facts_used == CONTEXT.facts


async def test_demo_exam_explanation():
    response = await DemoAIService().analyze_exam(CONTEXT, "Perfil lipídico\nColesterol LDL: 160 mg/dL (ref. ≤ 129 mg/dL) ALTO\n"
                                                            "Colesterol HDL: 50 mg/dL (ref. ≥ 40 mg/dL) NORMAL")
    assert "Colesterol LDL: 160 mg/dL (ref. ≤ 129 mg/dL) ALTO — fora da faixa" in response.text
    assert "a fração de colesterol transportada pelo LDL" in response.text
    assert "1 item(ns) fora da faixa" in response.text and "não significam, por si só, doença" in response.text


@pytest.mark.parametrize("text", ["Estou com dor no peito e suando", "Minha mãe DESMAIOU agora", "falta de ar forte"])
async def test_red_flags_trigger_urgent_guidance(text):
    for response in (await DemoAIService().analyze_symptoms(text, CONTEXT),
                     await DemoAIService().answer_question(text, CONTEXT, [])):
        assert response.urgent and "SAMU (192)" in response.text


async def test_demo_symptoms_without_red_flags_relate_to_record():
    response = await DemoAIService().analyze_symptoms("Tenho tosse e febre há dois dias", CONTEXT)
    assert not response.urgent
    assert "tosse, febre" in response.text or "febre, tosse" in response.text
    assert "Penicilina" in response.text  # alergia relevante para o profissional


@pytest.mark.parametrize("question,expected", [
    ("Quais alergias ela tem?", "Penicilina"),
    ("Quais remédios estão em uso?", "Losartana"),
    ("Como está a pressão?", "150 mmHg"),
    ("Tem algum exame alterado?", "LDL 160"),
    ("Qual o meu diagnóstico?", "Não posso emitir diagnósticos"),
])
async def test_demo_chat_intents(question, expected):
    response = await DemoAIService().answer_question(question, CONTEXT, [])
    assert expected in response.text and response.feature == AIFeature.CHAT


async def test_demo_chat_without_patient_asks_for_one():
    response = await DemoAIService().answer_question("Como está a pressão?", None, [])
    assert "Selecione um paciente" in response.text


# ----------------------------------------------------------- provedor Claude

class FakeMessages:
    def __init__(self, response=None, error=None):
        self.calls, self.response, self.error = [], response, error

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def fake_client(response=None, error=None):
    messages = FakeMessages(response, error)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def text_response(text, stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="thinking", thinking=""),
                                                             SimpleNamespace(type="text", text=text)])


async def test_claude_request_shape_and_minimal_context():
    client, messages = fake_client(text_response("Resumo fictício."))
    response = await ClaudeAIService(client=client).summarize_record(CONTEXT)
    call = messages.calls[0]
    assert call["model"] == DEFAULT_MODEL == "claude-opus-5-5"
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["output_config"] == {"effort": "low"} and "thinking" not in call
    assert AI_DISCLAIMER in call["system"][0]["text"] and "Nunca emita diagnóstico" in call["system"][0]["text"]
    content = call["messages"][0]["content"]
    assert "Maria, 46 anos" in content and "Penicilina" in content
    assert response.text == "Resumo fictício." and response.provider == "anthropic"


async def test_claude_chat_sends_history_with_fresh_context_on_last_turn():
    client, messages = fake_client(text_response("ok"))
    conversation = Conversation(title="t", created_at=NOW)
    conversation.add_user_message("Primeira pergunta", NOW)
    conversation.add_assistant_message(AIResponse("Primeira resposta", "anthropic", "m", AIFeature.CHAT), NOW)
    current = conversation.add_user_message("Segunda pergunta", NOW)
    await ClaudeAIService(client=client).answer_question(current.content, CONTEXT, conversation.messages)
    sent = messages.calls[0]["messages"]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[-1]["content"].startswith("Contexto do prontuário") and sent[-1]["content"].endswith("Segunda pergunta")


async def test_claude_refusal_and_unavailability():
    client, _ = fake_client(text_response("", stop_reason="refusal"))
    refused = await ClaudeAIService(client=client).generate_insights(CONTEXT)
    assert "Não posso ajudar" in refused.text

    sdk_error = type("APIConnectionError", (Exception,), {"__module__": "anthropic._exceptions"})
    client, _ = fake_client(error=sdk_error("sem rede"))
    with pytest.raises(AIUnavailableError):
        await ClaudeAIService(client=client).summarize_record(CONTEXT)
