from datetime import date, datetime
import uuid

import pytest

from app.application.interfaces.search_queries import SearchHit, SearchQueries
from app.application.use_cases.search_use_case import SearchUseCase, fold, mask_cpf
from app.domain.exceptions.common import BusinessRuleViolation
from app.infrastructure.persistence.repositories.sqlalchemy_search_queries import contains

PATIENT_ID = uuid.uuid4()


class FakeQueries(SearchQueries):
    def __init__(self):
        self.calls = []

    async def patients(self, text, digits, limit):
        self.calls.append(("patients", text, digits, limit))
        return [SearchHit(PATIENT_ID, "Maria Souza", {"cpf": "39053344705", "birth_date": date(1980, 10, 7)})], 3

    async def professionals(self, text, limit):
        return [], 0

    async def medications(self, text, limit):
        return [], 0

    async def exams(self, text, limit):
        return [], 0

    async def invoices(self, text, limit):
        return [], 0


def test_helpers():
    assert mask_cpf("39053344705") == "***.533.447-**" and mask_cpf("123") == "***"
    assert fold("Relatório de EXAMES") == "relatorio de exames"
    assert contains("50%_off\\") == "%50\\%\\_off\\\\%"  # curingas digitados viram texto


async def test_search_groups_masks_and_links():
    queries = FakeQueries()
    result = await SearchUseCase(queries, clock=lambda: datetime(2026, 10, 6)).search("  maria   390 ", per_group=2)
    assert result.query == "maria 390"
    assert queries.calls == [("patients", "maria 390", "390", 2)]
    group = result.groups[0]
    assert (group.key, group.total) == ("pacientes", 3)  # total do banco, mesmo mostrando só parte
    item = group.items[0]
    assert item.subtitle == "45 anos · CPF ***.533.447-**" and "39053344705" not in item.subtitle
    assert item.link == f"/app/prontuario?patient={PATIENT_ID}"
    assert [g.key for g in result.groups] == ["pacientes"]  # grupos vazios não aparecem


async def test_reports_are_matched_without_accents_and_short_terms_rejected():
    use_case = SearchUseCase(FakeQueries())
    result = await use_case.search("DISPENSAÇÕES")  # ignora acentos e caixa
    reports = next(g for g in result.groups if g.key == "relatorios")
    assert reports.items[0].link == "/app/relatorios?report=dispensacoes"
    queries = FakeQueries()
    await SearchUseCase(queries).search("ma")
    assert queries.calls[0][2] is None  # sem dígitos suficientes, não busca por CPF
    with pytest.raises(BusinessRuleViolation):
        await use_case.search(" a ")
