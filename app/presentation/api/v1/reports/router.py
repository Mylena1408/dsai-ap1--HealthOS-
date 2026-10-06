"""Relatórios em JSON, CSV e PDF."""
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.report_dto import ReportCatalogItemDTO, ReportDTO
from app.application.use_cases.report_use_case import ReportUseCase
from app.infrastructure.persistence.database import get_db
from app.infrastructure.reports.renderers import file_name, to_csv, to_pdf
from app.infrastructure.reports.sql_report_source import SQLAlchemyReportSource
from app.presentation.api.dependencies import get_events

router = APIRouter(prefix="/reports", tags=["Relatórios"])

MEDIA_TYPES = {"csv": "text/csv; charset=utf-8", "pdf": "application/pdf"}
RENDERERS = {"csv": to_csv, "pdf": to_pdf}


async def get_reports(session: AsyncSession = Depends(get_db), events=Depends(get_events)) -> ReportUseCase:
    return ReportUseCase(SQLAlchemyReportSource(session), events)


@router.get("", response_model=list[ReportCatalogItemDTO], summary="Relatórios disponíveis e seus filtros")
async def catalog(reports: ReportUseCase = Depends(get_reports)):
    return reports.catalog()


@router.get("/{report_key}", response_model=ReportDTO,
            summary="Gera um relatório (JSON para visualizar; CSV ou PDF para baixar)",
            responses={200: {"content": {"text/csv": {}, "application/pdf": {}}}})
async def generate(report_key: str,
                   start: Optional[date] = Query(None, description="Início do período (padrão: 30 dias até o fim)"),
                   end: Optional[date] = Query(None, description="Fim do período, inclusivo (padrão: hoje)"),
                   status: Optional[str] = Query(None, max_length=40),
                   format: Literal["json", "csv", "pdf"] = "json",
                   reports: ReportUseCase = Depends(get_reports)):
    table = await reports.generate(report_key, start, end, status, format)
    if format == "json":
        return ReportUseCase.to_dto(table)
    return Response(content=RENDERERS[format](table), media_type=MEDIA_TYPES[format],
                    headers={"Content-Disposition": f'attachment; filename="{file_name(table, format)}"'})
