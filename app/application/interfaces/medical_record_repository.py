from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from app.domain.entities.medical_record import (
    Allergy, ClinicalEvolution, Condition, Diagnosis, EvolutionStatus, PatientProfile, Procedure,
)
from app.domain.entities.patient import Patient
from app.domain.entities.timeline import TimelineEvent, TimelineEventType


@dataclass
class PatientSearch:
    query: Optional[str] = None  # trecho do nome, CPF (só dígitos) ou e-mail
    order_by: str = "name"       # "name" ou "recent"
    limit: int = 20
    offset: int = 0


class PatientDirectoryRepository(ABC):
    """Consultas de leitura sobre a tabela legada de pacientes."""

    @abstractmethod
    async def search(self, search: PatientSearch) -> tuple[list[Patient], int]: ...

    @abstractmethod
    async def get(self, patient_id: uuid.UUID) -> Optional[Patient]: ...


class MedicalRecordRepository(ABC):

    @abstractmethod
    async def get_profile(self, patient_id: uuid.UUID) -> Optional[PatientProfile]: ...

    @abstractmethod
    async def save_profile(self, profile: PatientProfile) -> PatientProfile:
        """Insere ou atualiza o perfil e sincroniza os contatos de emergência."""

    @abstractmethod
    async def list_allergies(self, patient_id: uuid.UUID) -> list[Allergy]: ...

    @abstractmethod
    async def get_allergy(self, allergy_id: uuid.UUID) -> Optional[Allergy]: ...

    @abstractmethod
    async def save_allergy(self, allergy: Allergy) -> Allergy: ...

    @abstractmethod
    async def list_conditions(self, patient_id: uuid.UUID) -> list[Condition]: ...

    @abstractmethod
    async def get_condition(self, condition_id: uuid.UUID) -> Optional[Condition]: ...

    @abstractmethod
    async def save_condition(self, condition: Condition) -> Condition: ...

    @abstractmethod
    async def list_diagnoses(self, patient_id: uuid.UUID) -> list[Diagnosis]: ...

    @abstractmethod
    async def get_diagnosis(self, diagnosis_id: uuid.UUID) -> Optional[Diagnosis]: ...

    @abstractmethod
    async def save_diagnosis(self, diagnosis: Diagnosis) -> Diagnosis: ...

    @abstractmethod
    async def list_procedures(self, patient_id: uuid.UUID) -> list[Procedure]: ...

    @abstractmethod
    async def save_procedure(self, procedure: Procedure) -> Procedure: ...

    @abstractmethod
    async def list_evolutions(self, patient_id: uuid.UUID) -> list[ClinicalEvolution]: ...

    @abstractmethod
    async def get_evolution(self, evolution_id: uuid.UUID) -> Optional[ClinicalEvolution]: ...

    @abstractmethod
    async def save_evolution(self, evolution: ClinicalEvolution,
                             expected_status: Optional[EvolutionStatus] = None) -> ClinicalEvolution:
        """Com `expected_status`, só grava se o registro ainda estiver nessa situação no banco
        (senão ConflictError): uma edição antiga não desfaz uma assinatura feita no meio tempo."""


@dataclass
class TimelineQuery:
    patient_id: uuid.UUID
    types: set[TimelineEventType] = field(default_factory=lambda: set(TimelineEventType))
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class TimelineRepository(ABC):

    @abstractmethod
    async def collect(self, query: TimelineQuery) -> list[TimelineEvent]:
        """Eventos de todas as fontes pedidas, dentro do período, em qualquer ordem."""
