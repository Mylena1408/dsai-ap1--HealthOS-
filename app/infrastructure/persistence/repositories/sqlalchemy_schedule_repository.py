from typing import List, Optional
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.domain.entities.schedule import Schedule, ScheduleStatus
from app.application.interfaces.schedule_repository import ScheduleRepository
from app.infrastructure.persistence.models.schedule_model import ScheduleModel

class SQLAlchemyScheduleRepository(ScheduleRepository):
    """
    Implementação do ScheduleRepository usando SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, schedule: Schedule) -> Schedule:
        db_schedule = ScheduleModel(
            id=schedule.id or uuid.uuid4(),
            doctor_id=schedule.doctor_id,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            status=schedule.status.value,
            patient_id=schedule.patient_id,
            notes=schedule.notes
        )
        self.session.add(db_schedule)
        await self.session.flush()
        schedule.id = db_schedule.id
        return schedule

    async def get_by_id(self, schedule_id: uuid.UUID) -> Optional[Schedule]:
        result = await self.session.get(ScheduleModel, schedule_id)
        if not result:
            return None
        return self._map_to_domain(result)

    async def get_doctor_schedule(self, doctor_id: uuid.UUID, start: datetime, end: datetime) -> List[Schedule]:
        stmt = select(ScheduleModel).where(
            and_(
                ScheduleModel.doctor_id == doctor_id,
                ScheduleModel.start_time >= start,
                ScheduleModel.end_time <= end
            )
        ).order_by(ScheduleModel.start_time)

        result = await self.session.execute(stmt)
        return [self._map_to_domain(s) for s in result.scalars().all()]

    async def find_overlapping_slots(self, doctor_id: uuid.UUID, start: datetime, end: datetime) -> List[Schedule]:
        """
        Busca slots que se sobrepõem ao intervalo fornecido.
        Lógica: (StartA < EndB) AND (EndA > StartB)
        """
        stmt = select(ScheduleModel).where(
            and_(
                ScheduleModel.doctor_id == doctor_id,
                ScheduleModel.start_time < end,
                ScheduleModel.end_time > start
            )
        )
        result = await self.session.execute(stmt)
        return [self._map_to_domain(s) for s in result.scalars().all()]

    async def update(self, schedule: Schedule) -> Schedule:
        db_schedule = await self.session.get(ScheduleModel, schedule.id)
        if not db_schedule:
            raise ValueError(f"Schedule slot {schedule.id} not found.")

        db_schedule.start_time = schedule.start_time
        db_schedule.end_time = schedule.end_time
        db_schedule.status = schedule.status.value
        db_schedule.patient_id = schedule.patient_id
        db_schedule.notes = schedule.notes
        db_schedule.updated_at = datetime.now()

        await self.session.flush()
        return schedule

    async def get_patient_schedule(self, patient_id: uuid.UUID) -> List[Schedule]:
        """Busca todos os agendamentos de um paciente com status BOOKED."""
        stmt = select(ScheduleModel).where(
            and_(
                ScheduleModel.patient_id == patient_id,
                ScheduleModel.status == ScheduleStatus.BOOKED.value
            )
        ).order_by(ScheduleModel.start_time)

        result = await self.session.execute(stmt)
        return [self._map_to_domain(s) for s in result.scalars().all()]

    async def delete(self, schedule_id: uuid.UUID) -> None:
        db_schedule = await self.session.get(ScheduleModel, schedule_id)
        if db_schedule:
            await self.session.delete(db_schedule)
            await self.session.flush()

    def _map_to_domain(self, db_model: ScheduleModel) -> Schedule:
        return Schedule(
            id=db_model.id,
            doctor_id=db_model.doctor_id,
            start_time=db_model.start_time,
            end_time=db_model.end_time,
            status=ScheduleStatus(db_model.status),
            patient_id=db_model.patient_id,
            notes=db_model.notes
        )
