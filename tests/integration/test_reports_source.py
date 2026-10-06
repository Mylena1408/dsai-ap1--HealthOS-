from datetime import date, datetime

from app.application.services.report_catalog import REPORTS
from app.application.use_cases.report_use_case import ReportUseCase
from app.infrastructure.reports.renderers import to_csv, to_pdf
from app.infrastructure.reports.sql_report_source import SQLAlchemyReportSource
from tests.integration.conftest import SEED_NOW

PERIOD = (date(2026, 1, 1), SEED_NOW.date())
DATE_COLUMN = {"consultas": "start_time", "exames": "requested_at", "dispensacoes": "dispensed_at",
               "faturas": "issue_date", "auditoria": "occurred_at"}


async def test_every_report_over_seeded_data(seeded):
    uc = ReportUseCase(SQLAlchemyReportSource(seeded["session"]), clock=lambda: SEED_NOW)
    for report in REPORTS:
        table = await uc.generate(report.key, *PERIOD, None, "csv")
        assert table.rows, report.key
        keys = {c.key for c in report.columns}
        assert all(set(row) == keys for row in table.rows), report.key
        if report.key in DATE_COLUMN:
            moments = [row[DATE_COLUMN[report.key]] for row in table.rows]
            as_date = [m.date() if isinstance(m, datetime) else m for m in moments]
            assert all(PERIOD[0] <= d <= PERIOD[1] for d in as_date), report.key
            assert as_date == sorted(as_date), report.key  # ordem cronológica
        assert to_csv(table) and to_pdf(table).startswith(b"%PDF")


async def test_status_filter_and_invoice_balance(seeded):
    uc = ReportUseCase(SQLAlchemyReportSource(seeded["session"]), clock=lambda: SEED_NOW)
    released = await uc.generate("exames", *PERIOD, "LIBERADO", "json")
    assert released.rows and all(r["status"] == "LIBERADO" and r["released_at"] for r in released.rows)

    invoices = await uc.generate("faturas", *PERIOD, None, "json")
    assert all(r["balance"] == r["gross_total"] - r["amount_paid"] for r in invoices.rows)
    overdue = await uc.generate("faturas", *PERIOD, "ATRASADO", "json")
    assert all(r["status"] == "ATRASADO" and r["due_date"] < SEED_NOW.date() for r in overdue.rows)

    stock = await uc.generate("estoque", None, None, None, "json")
    assert {r["situation"] for r in stock.rows} <= {"OK", "VENCENDO", "VENCIDO"}
    assert all(r["quantity"] > 0 for r in stock.rows)
