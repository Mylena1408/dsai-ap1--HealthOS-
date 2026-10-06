"""Histórico de atividades de um profissional: o que ele registrou no sistema, mais recente primeiro."""
from datetime import datetime
from typing import Callable
import uuid

from app.application.dtos.professional_dto import ActivityItemDTO, ProfessionalActivityDTO
from app.application.interfaces.professional_activity import ProfessionalActivityQueries
from app.application.use_cases.professional_use_case import ProfessionalUseCase


class ProfessionalActivityUseCase:
    def __init__(self, professionals: ProfessionalUseCase, queries: ProfessionalActivityQueries,
                 clock: Callable[[], datetime] = datetime.now):
        self.professionals = professionals
        self.queries = queries
        self.clock = clock

    async def activity(self, professional_id: uuid.UUID, limit: int) -> ProfessionalActivityDTO:
        await self.professionals.get(professional_id)  # 404 se o profissional não existir
        now = self.clock()  # consultas futuras ficam na agenda, não no histórico
        totals = await self.queries.totals(professional_id, now)
        items = await self.queries.recent(professional_id, now, limit)
        return ProfessionalActivityDTO(
            professional_id=professional_id,
            totals={kind.value: count for kind, count in totals.items() if count},
            items=[ActivityItemDTO(kind=i.kind.value, occurred_at=i.occurred_at, description=i.description,
                                   patient_id=i.patient_id, patient_name=i.patient_name) for i in items])
