"""Catálogo de relatórios (o "o quê"); as consultas ficam na fonte de dados (o "como")."""
from dataclasses import dataclass, field
from enum import Enum

from app.domain.entities.appointment import AppointmentStatus
from app.domain.entities.billing import BillingStatus
from app.domain.entities.laboratory import ExamStatus


class ColumnKind(Enum):
    TEXT = "texto"
    DATE = "data"
    DATETIME = "data_hora"
    MONEY = "moeda"
    NUMBER = "numero"
    CODE = "codigo"  # código do sistema (ex.: EM_PROCESSAMENTO); CSV/PDF mostram o rótulo legível


@dataclass(frozen=True)
class ReportColumn:
    key: str
    label: str
    kind: ColumnKind = ColumnKind.TEXT
    width: float = 1.0  # peso relativo da coluna no PDF


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    title: str
    description: str
    columns: tuple[ReportColumn, ...]
    uses_period: bool = True  # False: retrato do momento (ex.: estoque)
    status_options: tuple[str, ...] = field(default_factory=tuple)


C, K = ReportColumn, ColumnKind

REPORTS: tuple[ReportDefinition, ...] = (
    ReportDefinition(
        "consultas", "Consultas por período", "Consultas com início no período, com profissional, tipo e situação.",
        (C("start_time", "Início", K.DATETIME, 1.3), C("patient", "Paciente", width=2),
         C("professional", "Profissional", width=2), C("type", "Tipo", K.CODE), C("status", "Situação", K.CODE)),
        status_options=tuple(s.value for s in AppointmentStatus)),
    ReportDefinition(
        "exames", "Exames solicitados", "Exames solicitados no período e o andamento de cada um.",
        (C("requested_at", "Solicitado em", K.DATETIME, 1.3), C("patient", "Paciente", width=2),
         C("exam", "Exame", width=2), C("priority", "Prioridade", K.CODE), C("status", "Situação", K.CODE, 1.3),
         C("released_at", "Liberado em", K.DATETIME, 1.3)),
        status_options=tuple(s.value for s in ExamStatus)),
    ReportDefinition(
        "dispensacoes", "Dispensações de medicamentos", "Medicamentos entregues no período, por lote.",
        (C("dispensed_at", "Data", K.DATETIME, 1.3), C("patient", "Paciente", width=2),
         C("medication", "Medicamento", width=2), C("lot", "Lote"), C("quantity", "Quantidade", K.NUMBER),
         C("location", "Local", K.CODE))),
    ReportDefinition(
        "estoque", "Posição de estoque por lote", "Lotes com saldo na data de geração, com a situação da validade.",
        (C("medication", "Medicamento", width=2), C("lot", "Lote"), C("location", "Local", K.CODE),
         C("expiration_date", "Validade", K.DATE), C("quantity", "Saldo", K.NUMBER), C("situation", "Situação", K.CODE)),
        uses_period=False),
    ReportDefinition(
        "faturas", "Faturas emitidas", "Faturas emitidas no período, com valores pagos e saldo.",
        (C("number", "Número", width=1.8), C("patient", "Paciente", width=2), C("issue_date", "Emissão", K.DATE),
         C("due_date", "Vencimento", K.DATE), C("payer", "Pagador", width=1.6), C("gross_total", "Total", K.MONEY),
         C("amount_paid", "Pago", K.MONEY), C("balance", "Saldo", K.MONEY), C("status", "Situação", K.CODE, 1.5)),
        status_options=tuple(s.value for s in BillingStatus)),
    ReportDefinition(
        "auditoria", "Trilha de auditoria", "Eventos registrados no período (o que aconteceu, sem dados sensíveis).",
        (C("occurred_at", "Data", K.DATETIME, 1.3), C("event_type", "Evento", K.CODE, 2), C("entity_type", "Entidade"),
         C("summary", "Resumo", width=4))),
)

REPORTS_BY_KEY = {report.key: report for report in REPORTS}
