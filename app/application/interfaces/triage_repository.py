from abc import ABC, abstractmethod
from typing import List, Optional
import uuid
from datetime import datetime
from app.domain.entities.triage import Triage

class TriageRepository(ABC):
    """
    Interface de Repositório para a entidade Triage.
    """

    @abstractmethod
    async def save(self, triage: Triage) -> Triage:
        pass

    @abstractmethod
    async def get_by_patient(self, patient_id: uuid.UUID) -> Optional[Triage]:
        pass

    @abstractmethod
    async def get_latest_by_patient(self, patient_id: uuid.UUID) -> Optional[Triage]:
        pass

    @abstractmethod
    async def update(self, triage: Triage) -> Triage:
        pass

    @abstractmethod
    async def list_by_priority(self, priority: str) -> List[Triage]:
        pass
