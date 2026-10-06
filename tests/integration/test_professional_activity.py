import uuid

import pytest

from app.application.interfaces.professional_repository import ProfessionalFilters
from app.application.use_cases.professional_activity_use_case import ProfessionalActivityUseCase
from app.application.use_cases.professional_use_case import ProfessionalUseCase
from app.domain.entities.professional import ProfessionalType
from app.domain.exceptions.common import EntityNotFoundError
from app.infrastructure.persistence.repositories.sqlalchemy_professional_activity import SQLAlchemyProfessionalActivity
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyCatalogRepository, SQLAlchemyProfessionalRepository,
)
from tests.integration.conftest import SEED_NOW


@pytest.fixture
async def activity(seeded):
    s = seeded["session"]
    professionals = ProfessionalUseCase(SQLAlchemyProfessionalRepository(s), SQLAlchemyCatalogRepository(s))
    use_case = ProfessionalActivityUseCase(professionals, SQLAlchemyProfessionalActivity(s), clock=lambda: SEED_NOW)
    return use_case, professionals


async def first_of(professionals, kind):
    page = await professionals.search(ProfessionalFilters(professional_type=kind, limit=1))
    return page.items[0].id


async def test_history_by_role(activity):
    use_case, professionals = activity
    nurse = await use_case.activity(await first_of(professionals, ProfessionalType.NURSE), 10)
    assert nurse.totals.get("SINAIS_VITAIS", 0) > 0  # o seed registra as medições em nome da enfermagem
    assert any(i.kind == "SINAIS_VITAIS" and i.description.startswith("Sinais vitais") for i in nurse.items)

    doctor = await use_case.activity(await first_of(professionals, ProfessionalType.DOCTOR), 10)
    assert doctor.totals.get("CONSULTA", 0) > 0 and doctor.items
    pharmacist = await use_case.activity(await first_of(professionals, ProfessionalType.PHARMACIST), 10)
    assert pharmacist.totals.get("DISPENSACAO", 0) > 0

    for history in (nurse, doctor, pharmacist):
        moments = [i.occurred_at for i in history.items]
        assert moments == sorted(moments, reverse=True) and all(m <= SEED_NOW for m in moments)  # só o passado
        assert len(history.items) <= 10 and all(i.patient_name for i in history.items)


async def test_unknown_professional(activity):
    use_case, _ = activity
    with pytest.raises(EntityNotFoundError):
        await use_case.activity(uuid.uuid4(), 10)
