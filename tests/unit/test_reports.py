from datetime import date, datetime
from decimal import Decimal

import pytest

from app.application.interfaces.report_source import ReportSource
from app.application.services.events import InProcessPublisher
from app.application.services.report_catalog import REPORTS, ColumnKind
from app.application.use_cases.report_use_case import MAX_ROWS, ReportUseCase
from app.domain.events import EventType
from app.domain.exceptions.common import BusinessRuleViolation, EntityNotFoundError
from app.infrastructure.reports import sql_report_source
from app.infrastructure.reports.renderers import file_name, format_value, to_csv, to_pdf

NOW = datetime(2026, 10, 6, 15, 30)


class FakeSource(ReportSource):
    def __init__(self, rows=None):
        self.queries, self.rows_ = [], rows or []

    async def rows(self, report_key, query):
        self.queries.append((report_key, query))
        return self.rows_[:query.limit]


def use_case(rows=None):
    source, events = FakeSource(rows), InProcessPublisher()
    return ReportUseCase(source, events, clock=lambda: NOW), source, events


def test_every_report_has_a_query():
    for report in REPORTS:
        assert hasattr(sql_report_source.SQLAlchemyReportSource, f"_{report.key}"), report.key


async def test_period_defaults_and_validation():
    uc, source, _ = use_case()
    table = await uc.generate("consultas", None, None, None, "json")
    assert (table.start, table.end) == (date(2026, 9, 7), date(2026, 10, 6))  # 30 dias até hoje
    query = source.queries[0][1]
    assert query.start == datetime(2026, 9, 7) and query.end == datetime(2026, 10, 7)  # fim exclusivo

    with pytest.raises(BusinessRuleViolation, match="final"):
        await uc.generate("consultas", date(2026, 10, 2), date(2026, 10, 1), None, "json")
    with pytest.raises(BusinessRuleViolation, match="366"):
        await uc.generate("consultas", date(2025, 1, 1), date(2026, 1, 2), None, "json")
    with pytest.raises(BusinessRuleViolation, match="Situação"):
        await uc.generate("consultas", None, None, "PAGO", "json")
    with pytest.raises(EntityNotFoundError):
        await uc.generate("inexistente", None, None, None, "json")

    snapshot = await uc.generate("estoque", date(2026, 1, 1), date(2026, 2, 1), None, "json")
    assert snapshot.start is None and source.queries[-1][1].start is None  # retrato: ignora o período


async def test_row_limit_and_export_audit():
    rows = [{"summary": f"evento {i}"} for i in range(MAX_ROWS + 10)]
    uc, _, events = use_case(rows)
    table = await uc.generate("auditoria", None, None, None, "csv")
    assert len(table.rows) == MAX_ROWS and table.truncated
    event = events.published[0]
    assert event.event_type == EventType.REPORT_EXPORTED
    assert event.data == {"report": "auditoria", "format": "csv", "rows": MAX_ROWS, "status": None,
                          "start": "2026-09-07", "end": "2026-10-06"}
    assert "evento" not in event.summary  # registra a exportação, não o conteúdo


def test_brazilian_formatting():
    assert format_value(Decimal("1234.5"), ColumnKind.MONEY) == "1.234,50"
    assert format_value(30.0, ColumnKind.NUMBER) == "30" and format_value(2.5, ColumnKind.NUMBER) == "2,50"
    assert format_value(datetime(2026, 10, 6, 9, 5), ColumnKind.DATETIME) == "06/10/2026 09:05"
    assert format_value(date(2026, 10, 6), ColumnKind.DATE) == "06/10/2026"
    assert format_value("EM_PROCESSAMENTO", ColumnKind.CODE) == "Em processamento"
    assert format_value("NAO_COMPARECEU", ColumnKind.CODE) == "Não compareceu"
    assert format_value(None, ColumnKind.MONEY) == ""


async def test_csv_is_excel_friendly_and_blocks_formulas():
    uc, _, _ = use_case([
        {"number": "=HYPERLINK(\"x\")", "patient": "@Paciente", "issue_date": date(2026, 10, 1), "due_date": None,
         "payer": "Particular", "gross_total": Decimal("-10.00"), "amount_paid": Decimal(0), "balance": Decimal("1500"),
         "status": "ATRASADO"}])
    table = await uc.generate("faturas", date(2026, 10, 1), date(2026, 10, 6), None, "csv")
    content = to_csv(table)
    assert content.startswith("﻿".encode("utf-8"))
    lines = content.decode("utf-8-sig").splitlines()
    assert lines[0] == "Número;Paciente;Emissão;Vencimento;Pagador;Total;Pago;Saldo;Situação"
    # Texto vira literal (prefixo '); números negativos continuam números.
    assert lines[1] == "\"'=HYPERLINK(\"\"x\"\")\";'@Paciente;01/10/2026;;Particular;-10,00;0,00;1.500,00;Em atraso"
    assert file_name(table, "csv") == "healthos_faturas_20261001-20261006.csv"


async def test_pdf_is_generated_with_unicode_text():
    uc, _, _ = use_case([{"occurred_at": NOW, "event_type": "FATURA_EMITIDA", "entity_type": "Fatura",
                          "summary": "Valor ≤ limite — “ok” • ação"}])
    table = await uc.generate("auditoria", None, None, None, "pdf")
    assert ReportUseCase.to_dto(table).code_labels == {"FATURA_EMITIDA": "Fatura emitida"}  # rótulos para a tela
    pdf = to_pdf(table)
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
    empty = to_pdf(await use_case()[0].generate("estoque", None, None, None, "pdf"))
    assert empty.startswith(b"%PDF")
