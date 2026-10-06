from typing import List, Optional
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.domain.entities.triage import Triage, TriagePriority
from app.application.interfaces.triage_repository import TriageRepository
from app.infrastructure.persistence.models.triage_model import TriageModel

class SQLAlchemyTriageRepository(TriageRepository):
    """
    Implementação do TriageRepository utilizando SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, triage: Triage) -> Triage:
        db_triage = TriageModel(
            id=triage.id or uuid.uuid4(),
            patient_id=triage.patient_id,
            triage_nurse_id=triage.triage_nurse_id,
            priority=triage.priority.name,
            blood_pressure=triage.blood_pressure,
            heart_rate=triage.heart_rate,
            temperature=triage.temperature,
            oxygen_saturation=triage.oxygen_saturation,
            respiratory_rate=triage.respiratory_rate,
            main_complaint=triage.main_complaint,
            observations=triage.observations
        )
        self.session.add(db_triage)
        await self.session.flush()
        triage.id = db_triage.id
        return triage

    async def get_by_patient(self, patient_id: uuid.UUID) -> Optional[Triage]:
        return await self.get_latest_by_patient(patient_id)

    async def get_latest_by_patient(self, patient_id: uuid.UUID) -> Optional[Triage]:
        # Um paciente pode ter várias triagens; scalar_one_or_none falharia nesse caso.
        stmt = (select(TriageModel).where(TriageModel.patient_id == patient_id)
                .order_by(desc(TriageModel.created_at)).limit(1))
        result = await self.session.execute(stmt)
        db_triage = result.scalars().first()
        return self._map_to_domain(db_triage) if db_triage else None

    async def update(self, triage: Triage) -> Triage:
        db_triage = await self.session.get(TriageModel, triage.id)
        if not db_triage:
            raise ValueError(f"Triage record {triage.id} not found.")

        db_triage.priority = triage.priority.name
        db_triage.blood_pressure = triage.blood_pressure
        db_triage.heart_rate = triage.heart_rate
        db_triage.temperature = triage.temperature
        db_triage.oxygen_saturation = triage.oxygen_saturation
        db_triage.respiratory_rate = triage.respiratory_rate
        db_triage.main_complaint = triage.main_complaint
        db_triage.observations = triage.observations
        db_triage.updated_at = datetime.now()

        await self.session.flush()
        return triage

    async def list_by_priority(self, priority_name: str) -> List[Triage]:
        stmt = select(TriageModel).where(TriageModel.priority == priority_name)
        result = await self.session.execute(stmt)
        return [self._map_to_domain(t) for t in result.scalars().all()]

    def _map_to_domain(self, db_model: TriageModel) -> Triage:
        return Triage(
            id=db_model.id,
            patient_id=db_model.patient_id,
            triage_nurse_id=db_model.triage_nurse_id,
            priority=TriagePriority[db_model.priority],
            blood_pressure=db_model.blood_pressure,
            heart_rate=db_model.heart_rate,
            temperature=db_model.temperature,
            oxygen_saturation=db_model.oxygen_saturation,
            respiratory_rate=db_model.respiratory_rate,
            main_complaint=db_model.main_complaint,
            observations=db_model.observations,
            created_at=db_model.created_at,
            updated_at=db_model.updated_at
        )
