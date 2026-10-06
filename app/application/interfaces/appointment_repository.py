from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from app.domain.entities.appointment import Appointment, AppointmentStatus


@dataclass
class AppointmentFilters:
    patient_id: Optional[uuid.UUID] = None
    professional_id: Optional[uuid.UUID] = None
    statuses: list[AppointmentStatus] = field(default_factory=list)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    newest_first: bool = False
    limit: int = 20
    offset: int = 0


class AppointmentRepository(ABC):

    @abstractmethod
    async def save(self, appointment: Appointment) -> Appointment:
        """Insere ou atualiza a consulta e grava as mudanças de status ainda não persistidas."""

    @abstractmethod
    async def get_by_id(self, appointment_id: uuid.UUID) -> Optional[Appointment]: ...

    @abstractmethod
    async def find_active_overlapping(self, start: datetime, end: datetime, *,
                                      professional_id: Optional[uuid.UUID] = None,
                                      patient_id: Optional[uuid.UUID] = None,
                                      exclude_id: Optional[uuid.UUID] = None) -> list[Appointment]:
        """Consultas ativas que se sobrepõem a [start, end) para o profissional OU o paciente."""

    @abstractmethod
    async def search(self, filters: AppointmentFilters) -> tuple[list[Appointment], int]: ...

    @abstractmethod
    async def get_patient_names(self, patient_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]: ...
