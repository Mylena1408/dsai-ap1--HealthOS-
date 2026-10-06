"""Relatórios: valida os parâmetros, busca as linhas e registra a exportação na auditoria.

A formatação (CSV, PDF) fica na infraestrutura; aqui o resultado é uma tabela neutra.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Optional
import uuid

from app.application.dtos.report_dto import ReportCatalogItemDTO, ReportColumnDTO, ReportDTO
from app.application.interfaces.report_source import ReportQuery, ReportSource
from app.application.services.events import EventPublisher, NullPublisher
from app.application.services.report_catalog import REPORTS, REPORTS_BY_KEY, ColumnKind, ReportDefinition, code_label
from app.domain.events import DomainEvent, EventType
from app.domain.exceptions.common import BusinessRuleViolation, EntityNotFoundError

MAX_ROWS = 5000
MAX_PERIOD_DAYS = 366
DEFAULT_PERIOD_DAYS = 30
DISCLAIMER = "Relatório gerado a partir de dados fictícios do HealthOS (ambiente didático)."


@dataclass
class ReportTable:
    definition: ReportDefinition
    rows: list[dict[str, Any]]
    start: Optional[date]
    end: Optional[date]
    status: Optional[str]
    generated_at: datetime
    truncated: bool


def columns_dto(definition: ReportDefinition) -> list[ReportColumnDTO]:
    return [ReportColumnDTO(key=c.key, label=c.label, kind=c.kind.value) for c in definition.columns]


class ReportUseCase:
    def __init__(self, source: ReportSource, events: EventPublisher = NullPublisher(),
                 clock: Callable[[], datetime] = datetime.now):
        self.source = source
        self.events = events
        self.clock = clock

    def catalog(self) -> list[ReportCatalogItemDTO]:
        return [ReportCatalogItemDTO(key=r.key, title=r.title, description=r.description, columns=columns_dto(r),
                                     uses_period=r.uses_period, status_options=list(r.status_options),
                                     status_labels={c: code_label(c) for c in r.status_options})
                for r in REPORTS]

    async def generate(self, key: str, start: Optional[date], end: Optional[date], status: Optional[str],
                       export_format: str) -> ReportTable:
        definition = REPORTS_BY_KEY.get(key)
        if definition is None:
            raise EntityNotFoundError("Relatório", key)
        if status and status not in definition.status_options:
            raise BusinessRuleViolation(f"Situação inválida para este relatório: {status}.")
        now = self.clock()
        if definition.uses_period:
            end = end or now.date()
            start = start or end - timedelta(days=DEFAULT_PERIOD_DAYS - 1)
            if end < start:
                raise BusinessRuleViolation("A data final deve ser igual ou posterior à inicial.")
            if (end - start).days + 1 > MAX_PERIOD_DAYS:
                raise BusinessRuleViolation(f"O período máximo é de {MAX_PERIOD_DAYS} dias.")
        else:
            start = end = None

        rows = await self.source.rows(key, ReportQuery(
            start=datetime.combine(start, time.min) if start else None,
            end=datetime.combine(end + timedelta(days=1), time.min) if end else None,
            status=status, now=now, limit=MAX_ROWS + 1))
        table = ReportTable(definition, rows[:MAX_ROWS], start, end, status, now, truncated=len(rows) > MAX_ROWS)
        await self.events.publish(DomainEvent(
            event_type=EventType.REPORT_EXPORTED, occurred_at=now, entity_type="Relatório",
            entity_id=uuid.uuid5(uuid.NAMESPACE_URL, f"healthos/relatorios/{key}"),
            summary=f"Relatório \"{definition.title}\" gerado em {export_format.upper()} ({len(table.rows)} linha(s)).",
            data={"report": key, "format": export_format, "rows": len(table.rows), "status": status,
                  "start": start.isoformat() if start else None, "end": end.isoformat() if end else None}))
        return table

    @staticmethod
    def to_dto(table: ReportTable) -> ReportDTO:
        code_keys = [c.key for c in table.definition.columns if c.kind == ColumnKind.CODE]
        codes = {str(row[key]) for row in table.rows for key in code_keys if row.get(key) is not None}
        return ReportDTO(key=table.definition.key, title=table.definition.title, generated_at=table.generated_at,
                         start=table.start, end=table.end, status=table.status,
                         columns=columns_dto(table.definition), rows=table.rows, total_rows=len(table.rows),
                         truncated=table.truncated, code_labels={c: code_label(c) for c in sorted(codes)},
                         disclaimer=DISCLAIMER)
