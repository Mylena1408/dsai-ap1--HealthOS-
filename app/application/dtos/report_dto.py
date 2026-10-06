from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel


class ReportColumnDTO(BaseModel):
    key: str
    label: str
    kind: str


class ReportCatalogItemDTO(BaseModel):
    key: str
    title: str
    description: str
    columns: list[ReportColumnDTO]
    uses_period: bool
    status_options: list[str]
    status_labels: dict[str, str]


class ReportDTO(BaseModel):
    key: str
    title: str
    generated_at: datetime
    start: Optional[date]
    end: Optional[date]  # inclusivo
    status: Optional[str]
    columns: list[ReportColumnDTO]
    rows: list[dict[str, Any]]
    total_rows: int
    truncated: bool  # o limite de linhas foi atingido: refine o período
    code_labels: dict[str, str]  # rótulo legível de cada código presente nas colunas do tipo "codigo"
    disclaimer: str
