"""Catálogo das regras de alerta (o "o quê"); as consultas ficam no detector (o "como")."""
from dataclasses import dataclass

from app.domain.entities.inbox import Sector
from app.domain.entities.system_alert import AlertCategory


@dataclass(frozen=True)
class AlertRule:
    code: str
    category: AlertCategory
    description: str
    sector: Sector  # setor que recebe a notificação quando o alerta é aberto


# Parâmetros didáticos das regras
UPCOMING_APPOINTMENT_HOURS = 24
LOT_EXPIRY_WARNING_DAYS = 30
ABNORMAL_EXAM_WINDOW_DAYS = 30
CRITICAL_VITALS_WINDOW_DAYS = 7
FOLLOW_UP_GAP_DAYS = 180
INVOICE_OVERDUE_CRITICAL_DAYS = 30

RULES: list[AlertRule] = [
    AlertRule("ESTOQUE_BAIXO", AlertCategory.STOCK,
              "Estoque de um medicamento/local no limite mínimo ou abaixo dele (crítico se zerado).",
              Sector.PHARMACY),
    AlertRule("LOTE_VENCENDO", AlertCategory.MEDICATION,
              f"Lote com saldo vencendo em até {LOT_EXPIRY_WARNING_DAYS} dias (crítico se já vencido).",
              Sector.PHARMACY),
    AlertRule("CONSULTA_PROXIMA_NAO_CONFIRMADA", AlertCategory.APPOINTMENT,
              f"Consulta nas próximas {UPCOMING_APPOINTMENT_HOURS} horas ainda não confirmada.",
              Sector.RECEPTION),
    AlertRule("EXAME_FORA_REFERENCIA", AlertCategory.LABORATORY,
              f"Resultado liberado nos últimos {ABNORMAL_EXAM_WINDOW_DAYS} dias fora da faixa de referência "
              "(crítico se algum valor for crítico).", Sector.CLINICAL_COORDINATION),
    AlertRule("EXAME_ATRASADO", AlertCategory.LABORATORY,
              "Exame coletado cujo prazo de resultado já passou.", Sector.LABORATORY),
    AlertRule("SINAL_VITAL_CRITICO", AlertCategory.CLINICAL,
              f"Medição de sinais vitais com valor crítico nos últimos {CRITICAL_VITALS_WINDOW_DAYS} dias.",
              Sector.CLINICAL_COORDINATION),
    AlertRule("PACIENTE_SEM_ACOMPANHAMENTO", AlertCategory.CLINICAL,
              f"Paciente com condição ativa sem consulta finalizada há mais de {FOLLOW_UP_GAP_DAYS} dias "
              "e sem consulta futura.", Sector.CLINICAL_COORDINATION),
    AlertRule("FATURA_VENCIDA", AlertCategory.ADMINISTRATIVE,
              f"Fatura vencida com saldo em aberto (crítico após {INVOICE_OVERDUE_CRITICAL_DAYS} dias).",
              Sector.ADMINISTRATION),
]

RULES_BY_CODE = {rule.code: rule for rule in RULES}
