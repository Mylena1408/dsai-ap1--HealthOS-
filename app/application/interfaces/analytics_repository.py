from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import uuid

from app.domain.services.health_score import HealthScoreInputs


class AnalyticsRepository(ABC):
    """Consultas agregadas (somente leitura) para painéis e indicadores."""

    @abstractmethod
    async def health_inputs(self, now: datetime,
                            patient_ids: Optional[set[uuid.UUID]] = None) -> dict[uuid.UUID, HealthScoreInputs]:
        """Fatos do Health Score de vários pacientes de uma vez (todos, se `patient_ids` for None)."""

    @abstractmethod
    async def appointment_rows(self, date_from: datetime, date_to: datetime,
                               professional_id: Optional[uuid.UUID] = None) -> list[tuple[datetime, str]]:
        """(início, status) das consultas no período, para séries e contagens."""

    @abstractmethod
    async def distinct_patients_seen(self, professional_id: uuid.UUID, since: datetime) -> int: ...

    @abstractmethod
    async def exam_status_counts(self, since: Optional[datetime] = None,
                                 requested_by: Optional[uuid.UUID] = None) -> dict[str, int]: ...

    @abstractmethod
    async def released_exam_dates(self, since: datetime) -> list[datetime]: ...

    @abstractmethod
    async def dispensation_rows(self, since: datetime) -> list[tuple[datetime, str, float]]:
        """(data, medicamento, unidades) de cada linha dispensada desde `since`."""

    @abstractmethod
    async def entity_counts(self) -> dict[str, int]: ...

    @abstractmethod
    async def patient_registrations(self, since: datetime) -> list[datetime]: ...

    @abstractmethod
    async def prescriptions_since(self, since: datetime) -> dict[str, int]:
        """Prescrições emitidas desde `since`, por status."""
