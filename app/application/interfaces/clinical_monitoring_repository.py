from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from app.domain.entities.laboratory import (
    ExamPriority, ExamRequest, ExamResult, ExamStatus, ExamType, Laboratory,
)
from app.domain.entities.vital_signs import VitalSigns


class VitalSignsRepository(ABC):

    @abstractmethod
    async def save(self, vitals: VitalSigns) -> VitalSigns: ...

    @abstractmethod
    async def page(self, patient_id: uuid.UUID, date_from: Optional[datetime], date_to: Optional[datetime],
                   limit: int, offset: int) -> tuple[list[VitalSigns], int]:
        """Registros do mais recente para o mais antigo."""

    @abstractmethod
    async def history(self, patient_id: uuid.UUID, limit: int) -> list[VitalSigns]:
        """Últimos `limit` registros em ordem cronológica (para gráficos e tendências)."""

    @abstractmethod
    async def last_height(self, patient_id: uuid.UUID, until: datetime) -> Optional[float]: ...

    @abstractmethod
    async def height_history(self, patient_id: uuid.UUID) -> list[tuple[datetime, float]]:
        """Todas as alturas registradas, em ordem cronológica."""


@dataclass
class ExamRequestFilters:
    patient_id: Optional[uuid.UUID] = None
    statuses: list[ExamStatus] = field(default_factory=list)
    exam_type_id: Optional[uuid.UUID] = None
    requested_by: Optional[uuid.UUID] = None
    priority: Optional[ExamPriority] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    only_abnormal: bool = False
    newest_first: bool = True
    limit: int = 20
    offset: int = 0


@dataclass
class ExamRequestNames:
    """Nomes usados nas respostas, buscados em lote para evitar consultas N+1."""
    patients: dict[uuid.UUID, str] = field(default_factory=dict)
    professionals: dict[uuid.UUID, str] = field(default_factory=dict)
    exam_types: dict[uuid.UUID, ExamType] = field(default_factory=dict)
    laboratories: dict[uuid.UUID, str] = field(default_factory=dict)


class LaboratoryRepository(ABC):

    @abstractmethod
    async def list_exam_types(self) -> list[ExamType]: ...

    @abstractmethod
    async def get_exam_type(self, exam_type_id: uuid.UUID) -> Optional[ExamType]: ...

    @abstractmethod
    async def get_exam_type_by_code(self, code: str) -> Optional[ExamType]: ...

    @abstractmethod
    async def save_exam_type(self, exam_type: ExamType) -> ExamType: ...

    @abstractmethod
    async def list_laboratories(self) -> list[Laboratory]: ...

    @abstractmethod
    async def get_laboratory(self, laboratory_id: uuid.UUID) -> Optional[Laboratory]: ...

    @abstractmethod
    async def save_laboratory(self, laboratory: Laboratory) -> Laboratory: ...

    @abstractmethod
    async def save_request(self, request: ExamRequest) -> ExamRequest:
        """Insere ou atualiza; resultados são substituídos e o histórico só recebe acréscimos."""

    @abstractmethod
    async def get_request(self, request_id: uuid.UUID) -> Optional[ExamRequest]: ...

    @abstractmethod
    async def search_requests(self, filters: ExamRequestFilters) -> tuple[list[ExamRequest], int]: ...

    @abstractmethod
    async def names_for(self, requests: list[ExamRequest]) -> ExamRequestNames: ...

    @abstractmethod
    async def released_results(self, patient_id: uuid.UUID,
                               analyte_code: str) -> list[tuple[datetime, ExamResult]]:
        """Resultados LIBERADOS de um analito, em ordem cronológica de coleta."""
