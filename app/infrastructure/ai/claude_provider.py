"""Provedor opcional: Claude (Anthropic SDK). Ativado com AI_PROVIDER=anthropic.

Instale com `pip install -r requirements-ai.txt` e configure as credenciais do SDK
(ANTHROPIC_API_KEY ou `ant auth login`). O contexto enviado é o mínimo necessário do
paciente FICTÍCIO (sem CPF, e-mail, telefone ou endereço).
"""
from typing import Optional

from app.application.interfaces.ai_service import AIService, AIUnavailableError
from app.domain.entities.assistant import (
    AI_DISCLAIMER, AIFeature, AIResponse, ChatMessage, MessageRole, PatientContext,
)

DEFAULT_MODEL = "claude-opus-5-5"
HISTORY_LIMIT = 20
REFUSAL_TEXT = "Não posso ajudar com esse pedido. Para dúvidas de saúde, procure um profissional."

# Instruções estáveis no início do prompt, marcadas para cache. O cache só é aplicado acima de um
# tamanho mínimo de prefixo; com instruções curtas como estas, a marcação simplesmente não tem efeito.
SYSTEM_PROMPT = f"""Você é o assistente educacional do HealthOS, um sistema DIDÁTICO com dados fictícios.
Responda em português do Brasil, de forma clara e breve.
Regras:
- Nunca emita diagnóstico, prescrição ou mudança de dose. Você explica e organiza informações já registradas.
- Use apenas os fatos do contexto fornecido; se algo não estiver no contexto, diga que não há registro.
- Diante de sinais de alerta (dor no peito, falta de ar, desmaio, confusão, sangramento intenso, ideação
  suicida), oriente atendimento de urgência imediato (SAMU 192).
- Sugira perguntas que o paciente pode levar ao profissional quando fizer sentido.
- Termine com: "{AI_DISCLAIMER}" """

TASKS = {
    AIFeature.RECORD_SUMMARY: "Faça um resumo organizado do prontuário abaixo, por tópicos.",
    AIFeature.EXAM_ANALYSIS: "Explique, em linguagem acessível, o que cada item do exame avalia e quais estão fora da "
                             "faixa de referência, sem interpretar como diagnóstico.",
    AIFeature.SYMPTOMS: "O paciente descreveu sintomas. Organize as informações para a consulta, destaque sinais de "
                        "alerta se houver e relacione com alergias, condições e medicamentos registrados.",
    AIFeature.INSIGHTS: "Liste observações educacionais sobre o acompanhamento (consultas, exames, monitoramento).",
}


class ClaudeAIService(AIService):
    provider = "anthropic"

    def __init__(self, model: str = DEFAULT_MODEL, client=None):
        self.model = model
        self._client = client  # injetável nos testes

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise AIUnavailableError("SDK 'anthropic' não instalado (pip install -r requirements-ai.txt).") from exc
            self._client = anthropic.AsyncAnthropic()
        return self._client

    async def _complete(self, feature: AIFeature, messages: list[dict], facts) -> AIResponse:
        client = self._get_client()
        try:
            response = await client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
                output_config={"effort": "low"},
                # Em caso de recusa por política, a API tenta automaticamente um modelo de fallback.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except Exception as exc:  # erros do SDK (conexão, limite, status) -> indisponível
            if type(exc).__module__.startswith("anthropic"):
                raise AIUnavailableError(f"Provedor de IA indisponível: {type(exc).__name__}.") from exc
            raise
        if response.stop_reason == "refusal":
            return AIResponse(text=REFUSAL_TEXT, provider=self.provider, model=self.model, feature=feature)
        text = "\n".join(block.text for block in response.content if block.type == "text").strip()
        return AIResponse(text=text, provider=self.provider, model=self.model, feature=feature,
                          facts_used=list(facts))

    @staticmethod
    def _context_block(context: Optional[PatientContext]) -> str:
        return f"Contexto do prontuário:\n{context.as_text()}" if context else "Nenhum paciente selecionado."

    async def _task(self, feature: AIFeature, context: Optional[PatientContext], extra: str = "") -> AIResponse:
        content = f"{TASKS[feature]}\n\n{self._context_block(context)}" + (f"\n\n{extra}" if extra else "")
        return await self._complete(feature, [{"role": "user", "content": content}], context.facts if context else [])

    async def summarize_record(self, context):
        return await self._task(AIFeature.RECORD_SUMMARY, context)

    async def analyze_exam(self, context, exam_description):
        return await self._task(AIFeature.EXAM_ANALYSIS, context, f"Exame:\n{exam_description}")

    async def analyze_symptoms(self, description, context):
        return await self._task(AIFeature.SYMPTOMS, context, f"Descrição do paciente:\n{description}")

    async def generate_insights(self, context):
        return await self._task(AIFeature.INSIGHTS, context)

    async def answer_question(self, question, context, history: list[ChatMessage]):
        messages = [{"role": "user" if m.role == MessageRole.USER else "assistant", "content": m.content}
                    for m in history[-HISTORY_LIMIT:]]
        # A pergunta atual leva o contexto atualizado do prontuário.
        current = f"{self._context_block(context)}\n\nPergunta: {question}"
        if messages and messages[-1]["role"] == "user":
            messages[-1] = {"role": "user", "content": current}
        else:
            messages.append({"role": "user", "content": current})
        return await self._complete(AIFeature.CHAT, messages, context.facts if context else [])
