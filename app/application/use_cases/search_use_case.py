"""Busca global: um termo, resultados agrupados por tipo, cada um com o link da página certa."""
from datetime import datetime
from typing import Callable
import unicodedata

from app.application.dtos.search_dto import SearchGroupDTO, SearchItemDTO, SearchResultDTO
from app.application.interfaces.search_queries import SearchQueries
from app.application.services.code_labels import code_label
from app.application.services.report_catalog import REPORTS
from app.application.use_cases.medical_record_use_case import age_on
from app.domain.exceptions.common import BusinessRuleViolation

MIN_LENGTH = 2
MAX_LENGTH = 80
DEFAULT_PER_GROUP = 5


def mask_cpf(cpf: str) -> str:
    """Mostra só os dígitos centrais (***.456.789-**): suficiente para conferir, sem expor o documento."""
    digits = "".join(c for c in cpf if c.isdigit())
    return f"***.{digits[3:6]}.{digits[6:9]}-**" if len(digits) == 11 else "***"


def fold(text: str) -> str:
    """Minúsculas e sem acentos, para comparar textos que estão em memória."""
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn")


class SearchUseCase:
    def __init__(self, queries: SearchQueries, clock: Callable[[], datetime] = datetime.now):
        self.queries = queries
        self.clock = clock

    async def search(self, query: str, per_group: int = DEFAULT_PER_GROUP) -> SearchResultDTO:
        text = " ".join((query or "").split())
        if len(text) < MIN_LENGTH:
            raise BusinessRuleViolation(f"Digite ao menos {MIN_LENGTH} caracteres.")
        text = text[:MAX_LENGTH]
        digits = "".join(c for c in text if c.isdigit())
        today = self.clock().date()
        groups: list[SearchGroupDTO] = []

        def add(key: str, label: str, result: tuple[list, int], to_item: Callable) -> None:
            hits, total = result
            if total:
                groups.append(SearchGroupDTO(key=key, label=label, total=total, items=[to_item(h) for h in hits]))

        add("pacientes", "Pacientes",
            await self.queries.patients(text, digits if len(digits) >= 3 else None, per_group),
            lambda h: SearchItemDTO(title=h.title, link=f"/app/prontuario?patient={h.id}",
                                    subtitle=f"{age_on(h.details['birth_date'], today)} anos · CPF {mask_cpf(h.details['cpf'])}"))
        add("profissionais", "Profissionais", await self.queries.professionals(text, per_group),
            lambda h: SearchItemDTO(title=h.title, link=f"/app/consultas?professional={h.id}",
                                    subtitle=f"{code_label(h.details['type'])} · {h.details['registry']}"))
        add("medicamentos", "Medicamentos", await self.queries.medications(text, per_group),
            lambda h: SearchItemDTO(title=h.title, link="/app/farmacia",
                                    subtitle=f"{h.details['generic']} · {h.details['dosage']}"))
        add("exames", "Exames (código da amostra)", await self.queries.exams(text, per_group),
            lambda h: SearchItemDTO(title=h.title, link=f"/app/prontuario?patient={h.details['patient_id']}",
                                    subtitle=f"{h.details['patient']} · {code_label(h.details['status'])}"))
        add("faturas", "Faturas", await self.queries.invoices(text, per_group),
            lambda h: SearchItemDTO(title=h.title, link=f"/app/financeiro?invoice={h.id}", subtitle=h.details["patient"]))

        needle = fold(text)
        reports = [r for r in REPORTS if needle in fold(f"{r.title} {r.description}")]
        add("relatorios", "Relatórios", (reports[:per_group], len(reports)),
            lambda r: SearchItemDTO(title=r.title, subtitle=r.description, link=f"/app/relatorios?report={r.key}"))
        return SearchResultDTO(query=text, groups=groups)
