from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class ReportQuery:
    start: Optional[datetime]  # inclusivo
    end: Optional[datetime]    # exclusivo
    status: Optional[str]
    now: datetime
    limit: int


class ReportSource(ABC):
    @abstractmethod
    async def rows(self, report_key: str, query: ReportQuery) -> list[dict[str, Any]]:
        """Linhas do relatório (chaves = colunas do catálogo), em ordem de apresentação, até `query.limit`."""
