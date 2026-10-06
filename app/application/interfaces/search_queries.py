from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass(frozen=True)
class SearchHit:
    id: uuid.UUID
    title: str
    details: dict = field(default_factory=dict)  # campos usados pelo caso de uso para montar o subtítulo e o link


class SearchQueries(ABC):
    """Cada método devolve (até `limit` resultados, total de correspondências)."""

    @abstractmethod
    async def patients(self, text: str, digits: Optional[str], limit: int) -> tuple[list[SearchHit], int]:
        """Por trecho do nome ou, se houver dígitos, do CPF."""

    @abstractmethod
    async def professionals(self, text: str, limit: int) -> tuple[list[SearchHit], int]:
        """Por trecho do nome ou do registro profissional."""

    @abstractmethod
    async def medications(self, text: str, limit: int) -> tuple[list[SearchHit], int]:
        """Por nome comercial ou princípio ativo."""

    @abstractmethod
    async def exams(self, text: str, limit: int) -> tuple[list[SearchHit], int]:
        """Por código de amostra (ex.: AM...)."""

    @abstractmethod
    async def invoices(self, text: str, limit: int) -> tuple[list[SearchHit], int]:
        """Por número da fatura."""
