"""Provedor DEMO_AI: respostas determinísticas montadas a partir dos fatos do prontuário.

Não usa rede nem modelo de linguagem. Serve para a demonstração funcionar sem custo e
para os testes serem reprodutíveis. Nunca diagnostica: organiza, explica e sugere
perguntas para levar ao profissional.
"""
import re
import unicodedata
from typing import Optional

from app.application.interfaces.ai_service import AIService
from app.domain.entities.assistant import AIFeature, AIResponse, ChatMessage, ContextFact, PatientContext

# O que cada analito mede (texto educacional genérico, sem interpretação individual).
ANALYTE_NOTES = {
    "hemoglobina": "a proteína das hemácias que transporta oxigênio",
    "hematocrito": "a proporção do sangue ocupada pelas hemácias",
    "leucocitos": "as células de defesa do sangue",
    "plaquetas": "as células que participam da coagulação",
    "glicose": "a quantidade de açúcar no sangue no momento da coleta",
    "hemoglobina glicada": "a média aproximada da glicose nos últimos meses",
    "colesterol total": "a soma das frações de colesterol no sangue",
    "colesterol hdl": "a fração de colesterol transportada pelo HDL",
    "colesterol ldl": "a fração de colesterol transportada pelo LDL",
    "triglicerideos": "um tipo de gordura circulante no sangue",
    "creatinina": "um resíduo muscular usado para estimar a filtração dos rins",
    "ureia": "um resíduo do metabolismo das proteínas eliminado pelos rins",
    "potassio": "um mineral importante para músculos e coração",
    "tsh": "o hormônio que regula a tireoide",
    "t4 livre": "o hormônio da tireoide disponível no sangue",
    "25-hidroxivitamina d": "a reserva de vitamina D do organismo",
}

# Sinais de alerta: a resposta passa a orientar atendimento imediato.
RED_FLAGS = ["dor no peito", "falta de ar", "desmaio", "desmaiou", "convulsao", "sangramento intenso",
             "fraqueza subita", "boca torta", "confusao mental", "dificuldade para respirar", "labios roxos",
             "vomito com sangue", "pensamentos suicidas"]
URGENT_TEXT = ("Os sintomas descritos incluem sinais de alerta. Procure atendimento de urgência agora "
               "ou ligue para o SAMU (192). Esta orientação é educacional e não substitui avaliação profissional.")

SYMPTOM_TOPICS = {
    "febre": "febre", "tosse": "tosse", "dor de cabeca": "dor de cabeça", "tontura": "tontura",
    "nausea": "náusea", "diarreia": "diarreia", "dor de garganta": "dor de garganta", "cansaco": "cansaço",
    "dor nas costas": "dor nas costas", "falta de apetite": "falta de apetite",
}

INTENTS = [
    (("alergi",), "Alergia", "Alergias registradas"),
    (("medic", "remedio", "receita", "prescri"), "Medicamento", "Medicamentos em uso"),
    (("exame", "resultado", "laborat"), "Exame", "Exames recentes"),
    (("pressao", "glicemia", "peso", "imc", "temperatura", "sinal", "sinais", "saturacao", "frequencia"),
     "Sinal vital", "Últimos sinais vitais"),
    (("consulta", "agenda", "retorno", "marcad"), "Consulta", "Consultas"),
    (("score", "acompanhamento", "indicador"), "Health Score", "Health Score (indicador demonstrativo)"),
    (("condic", "doenca", "diagnost", "problema"), "Condição", "Condições e diagnósticos registrados"),
]


def normalize(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", plain).strip()


def _bullets(facts: list[ContextFact]) -> str:
    return "\n".join(f"• {f.text}" for f in facts)


class DemoAIService(AIService):
    provider = "demo"
    model = "regras-deterministicas"

    def _response(self, feature: AIFeature, text: str, facts: list[ContextFact] = (), suggestions=(),
                  urgent: bool = False) -> AIResponse:
        return AIResponse(text=text, provider=self.provider, model=self.model, feature=feature,
                          facts_used=list(facts), suggestions=list(suggestions), urgent=urgent)

    async def summarize_record(self, context: PatientContext) -> AIResponse:
        sections = []
        for category, title in (("Alergia", "Alergias"), ("Condição", "Condições"), ("Medicamento", "Medicamentos em uso"),
                                ("Exame", "Exames"), ("Sinal vital", "Sinais vitais"), ("Consulta", "Consultas"),
                                ("Health Score", "Acompanhamento")):
            facts = context.by_category(category)
            if facts:
                sections.append(f"{title}:\n{_bullets(facts)}")
        body = "\n\n".join(sections) if sections else "Ainda não há registros clínicos para resumir."
        return self._response(
            AIFeature.RECORD_SUMMARY, f"Resumo organizado do prontuário de {context.first_name} ({context.age} anos):\n\n{body}",
            context.facts, ["Quais exames estão fora da referência?", "Quais medicamentos estão em uso?",
                            "Como está o acompanhamento?"])

    async def analyze_exam(self, context: PatientContext, exam_description: str) -> AIResponse:
        lines = []
        for raw in exam_description.splitlines():
            name = normalize(raw.split(":")[0])
            note = ANALYTE_NOTES.get(name)
            status = "fora da faixa de referência" if any(w in raw for w in ("ALTO", "BAIXO", "CRITICO")) else "dentro da faixa de referência"
            if ":" in raw:
                lines.append(f"• {raw.strip()} — {status}" + (f". Este exame avalia {note}." if note else "."))
        altered = sum("fora da faixa" in line for line in lines)
        conclusion = (f"{altered} item(ns) fora da faixa de referência. Valores fora da faixa não significam, por si só, "
                      "doença: dependem de contexto, repetição e avaliação clínica." if altered
                      else "Todos os itens estão dentro das faixas de referência ilustrativas.")
        return self._response(
            AIFeature.EXAM_ANALYSIS, "Explicação educacional do exame:\n\n" + "\n".join(lines) + f"\n\n{conclusion}",
            context.by_category("Exame"),
            ["O que perguntar ao médico sobre este resultado?", "Há exames anteriores para comparar?"])

    async def analyze_symptoms(self, description: str, context: Optional[PatientContext]) -> AIResponse:
        text = normalize(description)
        flags = [flag for flag in RED_FLAGS if flag in text]
        if flags:
            return self._response(AIFeature.SYMPTOMS, URGENT_TEXT, urgent=True)
        topics = [label for key, label in SYMPTOM_TOPICS.items() if key in text]
        relevant = (context.by_category("Alergia") + context.by_category("Condição")
                    + context.by_category("Medicamento")) if context else []
        parts = [f"Sintomas mencionados: {', '.join(topics)}." if topics else "Registrei a descrição dos sintomas."]
        parts.append("Para a conversa com o profissional, vale anotar: quando começou, intensidade (0 a 10), "
                     "o que piora ou melhora, se há febre medida e quais medicamentos foram usados.")
        if relevant:
            parts.append("Informações do prontuário que o profissional pode querer considerar:\n" + _bullets(relevant))
        parts.append("Procure atendimento imediato se surgirem falta de ar, dor no peito, desmaio, confusão ou piora rápida.")
        return self._response(AIFeature.SYMPTOMS, "\n\n".join(parts), relevant,
                              ["Como me preparar para a consulta?", "Quais medicamentos estão em uso?"])

    async def generate_insights(self, context: PatientContext) -> AIResponse:
        observations = []
        abnormal_exams = [f for f in context.by_category("Exame") if "fora da referência" in f.text]
        altered_vitals = [f for f in context.by_category("Sinal vital") if "alterad" in f.text]
        if abnormal_exams:
            observations.append(f"Há {len(abnormal_exams)} resultado(s) recente(s) fora da referência — bom tema para o próximo retorno.")
        if altered_vitals:
            observations.append("Algumas medidas recentes de sinais vitais estão fora da faixa ilustrativa; acompanhar a tendência.")
        if not context.by_category("Consulta") or all("Próxima" not in f.text for f in context.by_category("Consulta")):
            observations.append("Não há consulta futura registrada; se houver condição em acompanhamento, considerar agendar retorno.")
        if context.by_category("Alergia"):
            observations.append("Alergias registradas devem ser lembradas em toda nova prescrição.")
        score = context.by_category("Health Score")
        if score:
            observations.append(score[0].text)
        text = "Observações educacionais a partir dos registros:\n\n" + (
            _bullets([ContextFact("Obs", o) for o in observations]) if observations else "Nenhuma observação relevante.")
        return self._response(AIFeature.INSIGHTS, text, context.facts, ["Resuma o prontuário", "Explique o Health Score"])

    async def answer_question(self, question: str, context: Optional[PatientContext],
                              history: list[ChatMessage]) -> AIResponse:
        text = normalize(question)
        if any(flag in text for flag in RED_FLAGS):
            return self._response(AIFeature.CHAT, URGENT_TEXT, urgent=True)
        if context is None:
            return self._response(AIFeature.CHAT, "Selecione um paciente fictício para que eu possa responder com base "
                                  "no prontuário. Posso resumir registros, explicar exames e organizar dúvidas para a consulta.",
                                  suggestions=["Como funciona o assistente?"])
        if "resum" in text:
            summary = await self.summarize_record(context)
            summary.feature = AIFeature.CHAT
            return summary
        if "diagnost" in text and ("qual" in text or "tenho" in text):
            return self._response(AIFeature.CHAT, "Não posso emitir diagnósticos. Posso listar as condições e "
                                  "diagnósticos já registrados pelos profissionais no prontuário fictício:\n\n"
                                  + (_bullets(context.by_category("Condição")) or "Nenhum registro."),
                                  context.by_category("Condição"), ["Quais exames estão fora da referência?"])
        for keywords, category, title in INTENTS:
            if any(k in text for k in keywords):
                facts = context.by_category(category)
                answer = f"{title} de {context.first_name}:\n\n{_bullets(facts)}" if facts else \
                    f"Não encontrei registros de {title.lower()} para {context.first_name}."
                return self._response(AIFeature.CHAT, answer, facts, self._follow_ups(category))
        return self._response(AIFeature.CHAT, "No modo demonstrativo, respondo sobre alergias, medicamentos, exames, "
                              "sinais vitais, consultas, condições e o Health Score do paciente selecionado.",
                              suggestions=["Resuma o prontuário", "Quais exames estão fora da referência?",
                                           "Quais medicamentos estão em uso?"])

    @staticmethod
    def _follow_ups(category: str) -> list[str]:
        options = {
            "Exame": ["Explique o que esses exames avaliam", "Quando foi a última consulta?"],
            "Medicamento": ["Há alergias registradas?", "Resuma o prontuário"],
            "Sinal vital": ["Como está o Health Score?", "Quais exames estão fora da referência?"],
        }
        return options.get(category, ["Resuma o prontuário", "Quais medicamentos estão em uso?"])
