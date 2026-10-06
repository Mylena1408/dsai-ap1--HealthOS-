"""Health Score — indicador DEMONSTRATIVO de acompanhamento (não é diagnóstico).

Mede o quanto o paciente fictício está sendo acompanhado (comparecimento, exames
concluídos, medicamentos retirados, monitoramento e seguimento), não o quanto é
saudável. Cada componente vale de 0 a 100; componentes sem dados são "não aplicáveis"
e ficam fora da média, para que a ausência de informação não seja punida.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional

DISCLAIMER = ("Indicador demonstrativo de acompanhamento, calculado com dados fictícios. "
              "Não é diagnóstico e não substitui avaliação profissional.")

RECENT_VITALS_TARGET = 3          # medições nos últimos 90 dias
FOLLOW_UP_GOOD_DAYS = 180
FOLLOW_UP_FAIR_DAYS = 365


class ScoreBand(Enum):
    GOOD = "BOM"                  # >= 80
    ATTENTION = "ATENCAO"         # 60–79
    INSUFFICIENT = "INSUFICIENTE"  # < 60


@dataclass
class HealthScoreInputs:
    """Fatos agregados de um paciente (janelas: 12 meses para consultas/exames, 90 dias para o resto)."""
    completed_appointments: int = 0
    no_show_appointments: int = 0
    last_completed_appointment: Optional[datetime] = None
    has_upcoming_appointment: bool = False
    exams_requested: int = 0          # não cancelados
    exams_released: int = 0
    exams_overdue: int = 0            # coletados com prazo vencido
    critical_exam_results: int = 0    # analitos críticos em resultados liberados
    prescribed_quantity: float = 0    # itens em uso ou concluídos de prescrições não canceladas
    dispensed_quantity: float = 0
    vitals_recent: int = 0
    latest_vitals_abnormal_ratio: Optional[float] = None
    active_conditions: int = 0


@dataclass
class ScoreComponent:
    key: str
    label: str
    score: Optional[int]  # None = não aplicável
    explanation: str

    @property
    def applicable(self) -> bool:
        return self.score is not None


@dataclass
class HealthScore:
    score: Optional[int]
    band: Optional[ScoreBand]
    components: list[ScoreComponent] = field(default_factory=list)
    disclaimer: str = DISCLAIMER


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def _appointments(i: HealthScoreInputs) -> ScoreComponent:
    attended = i.completed_appointments + i.no_show_appointments
    if not attended:
        return ScoreComponent("consultas", "Consultas", None, "Nenhuma consulta realizada ou perdida nos últimos 12 meses.")
    rate = i.completed_appointments / attended
    return ScoreComponent("consultas", "Consultas", _clamp(rate * 100),
                          f"Compareceu a {i.completed_appointments} de {attended} consulta(s) nos últimos 12 meses.")


def _exams(i: HealthScoreInputs) -> ScoreComponent:
    if not i.exams_requested:
        return ScoreComponent("exames", "Exames", None, "Nenhum exame solicitado nos últimos 12 meses.")
    completion = i.exams_released / i.exams_requested * 100
    penalty = min(i.exams_overdue * 10, 30)
    text = f"{i.exams_released} de {i.exams_requested} exame(s) com resultado liberado"
    if i.exams_overdue:
        text += f"; {i.exams_overdue} atrasado(s)"
    if i.critical_exam_results:
        text += f"; {i.critical_exam_results} valor(es) crítico(s) que pedem acompanhamento"
    return ScoreComponent("exames", "Exames", _clamp(completion - penalty), text + ".")


def _medications(i: HealthScoreInputs) -> ScoreComponent:
    if not i.prescribed_quantity:
        return ScoreComponent("medicamentos", "Medicamentos", None, "Sem prescrições recentes.")
    coverage = min(i.dispensed_quantity / i.prescribed_quantity, 1)
    return ScoreComponent("medicamentos", "Medicamentos", _clamp(coverage * 100),
                          f"Retirou {coverage:.0%} das quantidades prescritas nos últimos 90 dias.")


def _monitoring(i: HealthScoreInputs) -> ScoreComponent:
    if not i.vitals_recent and i.latest_vitals_abnormal_ratio is None:
        return ScoreComponent("monitoramento", "Monitoramento", 0,
                              "Nenhuma medição de sinais vitais nos últimos 90 dias.")
    regularity = min(i.vitals_recent / RECENT_VITALS_TARGET, 1) * 60
    stability = (1 - (i.latest_vitals_abnormal_ratio or 0)) * 40
    return ScoreComponent("monitoramento", "Monitoramento", _clamp(regularity + stability),
                          f"{i.vitals_recent} medição(ões) em 90 dias; "
                          f"{(i.latest_vitals_abnormal_ratio or 0):.0%} das medidas da última aferição fora da referência.")


def _follow_up(i: HealthScoreInputs, today: date) -> ScoreComponent:
    last = i.last_completed_appointment
    days = (today - last.date()).days if last else None
    if days is not None and days <= FOLLOW_UP_GOOD_DAYS:
        score, text = 100, f"Última consulta há {days} dia(s)."
    elif days is not None and days <= FOLLOW_UP_FAIR_DAYS:
        score, text = 60, f"Última consulta há {days} dias."
    else:
        score, text = 20, "Sem consulta finalizada no último ano."
    if i.has_upcoming_appointment:
        score, text = min(100, score + 20), text + " Há consulta futura agendada."
    if i.active_conditions and days is not None and days > FOLLOW_UP_GOOD_DAYS and not i.has_upcoming_appointment:
        text += f" Possui {i.active_conditions} condição(ões) ativa(s) sem retorno marcado."
    return ScoreComponent("acompanhamento", "Acompanhamento", score, text)


def compute_health_score(inputs: HealthScoreInputs, today: date) -> HealthScore:
    components = [_appointments(inputs), _exams(inputs), _medications(inputs), _monitoring(inputs),
                  _follow_up(inputs, today)]
    applicable = [c.score for c in components if c.applicable]
    score = _clamp(sum(applicable) / len(applicable)) if applicable else None
    band = None if score is None else (ScoreBand.GOOD if score >= 80
                                       else ScoreBand.ATTENTION if score >= 60 else ScoreBand.INSUFFICIENT)
    return HealthScore(score=score, band=band, components=components)
