"""Harness de avaliação do assistente (SPEC/2026-10-19-harness-assistente.md)."""
from datetime import datetime

from app.application.dtos.assistant_dto import ExchangeDTO
from app.application.use_cases.assistant_harness_use_case import CASES, AssistantHarness
from app.application.use_cases.assistant_use_case import AssistantUseCase, _message_dto
from app.domain.entities.assistant import AIFeature, AIResponse
from app.infrastructure.ai.demo_provider import DemoAIService

RAN_AT = datetime(2026, 10, 19, 9, 30)


class RealProviderStub(DemoAIService):
    """Finge ser um provedor real: o harness não deve chamá-lo nos casos de comportamento."""
    provider = "anthropic"
    model = "claude-opus-5-5"

    async def analyze_symptoms(self, description, context):
        raise AssertionError("o harness não deve chamar o provedor real")

    async def answer_question(self, question, context, history):
        raise AssertionError("o harness não deve chamar o provedor real")


class UnsafeAssistant(AssistantUseCase):
    """Caso de uso sem a regra de segurança: tudo vai direto ao provedor."""

    async def symptoms(self, description, patient_id):
        context = await self.contexts.build(patient_id) if patient_id else None
        return await self._run(AIFeature.SYMPTOMS, patient_id, self.ai.analyze_symptoms(description, context))

    async def send_message(self, conversation_id, content):
        conversation = await self._conversation(conversation_id)
        user_message = conversation.add_user_message(content, self.clock())
        response = await self.ai.answer_question(user_message.content, None, [user_message])
        assistant_message = conversation.add_assistant_message(response, self.clock())
        await self.conversations.save(conversation)
        return ExchangeDTO(user_message=_message_dto(user_message), assistant_message=_message_dto(assistant_message),
                           disclaimer=response.disclaimer)


class EchoAI(DemoAIService):
    """Provedor que responde normalmente a qualquer texto (sem regra própria de alerta)."""

    async def analyze_symptoms(self, description, context):
        return AIResponse("Anotado.", self.provider, self.model, AIFeature.SYMPTOMS)

    async def answer_question(self, question, context, history):
        return AIResponse("Anotado.", self.provider, self.model, AIFeature.CHAT)


async def test_demo_passes_all_nine_cases():
    report = await AssistantHarness(DemoAIService(), clock=lambda: RAN_AT).run()
    assert (report.total, report.passed, report.failed, report.skipped) == (9, 9, 0, 0)
    assert report.provider == "demo" and report.demo_mode and report.ran_at == RAN_AT
    assert [c.code for c in report.cases] == [c.code for c in CASES]
    assert all(c.status == "APROVADO" and c.checks for c in report.cases)


async def test_provider_is_called_only_in_behavior_cases():
    report = await AssistantHarness(DemoAIService()).run()
    for case in report.cases:
        called = next(c for c in case.checks if c.name.startswith("Provedor de IA"))
        assert called.passed
        assert ("não chamado" in case.obtained) == (case.group == "SEGURANCA")


async def test_unsafe_assistant_fails_safety_cases():
    report = await AssistantHarness(EchoAI(), assistant_factory=UnsafeAssistant).run()
    safety = [c for c in report.cases if c.group == "SEGURANCA"]
    assert safety and all(c.status == "REPROVADO" for c in safety)
    failed = {check.name for check in safety[0].checks if not check.passed}
    assert {"Orientação de urgência", "Provedor de IA não chamado"} <= failed
    assert report.failed >= len(safety)


async def test_real_provider_skips_behavior_cases_and_still_checks_safety():
    report = await AssistantHarness(RealProviderStub()).run()
    assert (report.passed, report.failed, report.skipped) == (5, 0, 4)
    assert not report.demo_mode
    assert all(c.status == "PULADO" for c in report.cases if c.group == "COMPORTAMENTO")
