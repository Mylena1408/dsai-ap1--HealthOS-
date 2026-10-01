from abc import ABC, abstractmethod
from typing import List, Optional
import uuid
from datetime import datetime
from app.domain.entities.schedule import Schedule

class ScheduleRepository(ABC):
    """
    Interface de Repositório para a entidade Schedule.
    """

    @abstractmethod
    async def save(self, schedule: Schedule) -> Schedule:
        pass

    @abstractmethod
    async def get_by_id(self, schedule_id: uuid.UUID) -> Optional[Schedule]:
        pass

    @abstractmethod
    async def get_doctor_schedule(self, doctor_id: uuid.UUID, start: datetime, end: datetime) -> List[Schedule]:
        pass

    @abstractmethod
    async def find_overlapping_slots(self, doctor_id: uuid.UUID, start: datetime, end: datetime) -> List[Schedule]:
        pass

    @abstractmethod
    async def update(self, schedule: Schedule) -> Schedule:
        pass

    @abstractmethod
    async def get_patient_schedule(self, patient_id: uuid.UUID) -> List[Schedule]:
        pass

    @abstractmethod
    async def delete(self, schedule_id: uuid.UUID) -> None:
        pass
