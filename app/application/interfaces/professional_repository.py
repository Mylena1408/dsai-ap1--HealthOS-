from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import uuid

from app.domain.entities.professional import (
    Department, Professional, ProfessionalStatus, ProfessionalType, Specialty,
)


@dataclass
class ProfessionalFilters:
    query: Optional[str] = None  # trecho do nome ou do registro
    professional_type: Optional[ProfessionalType] = None
    status: Optional[ProfessionalStatus] = None
    department_id: Optional[uuid.UUID] = None
    specialty_id: Optional[uuid.UUID] = None
    limit: int = 20
    offset: int = 0


class CatalogRepository(ABC):
    """Departamentos e especialidades (cadastros de apoio)."""

    @abstractmethod
    async def save_department(self, department: Department) -> Department: ...

    @abstractmethod
    async def get_department(self, department_id: uuid.UUID) -> Optional[Department]: ...

    @abstractmethod
    async def get_department_by_name(self, name: str) -> Optional[Department]: ...

    @abstractmethod
    async def list_departments(self) -> list[Department]: ...

    @abstractmethod
    async def save_specialty(self, specialty: Specialty) -> Specialty: ...

    @abstractmethod
    async def get_specialty(self, specialty_id: uuid.UUID) -> Optional[Specialty]: ...

    @abstractmethod
    async def get_specialty_by_name(self, name: str) -> Optional[Specialty]: ...

    @abstractmethod
    async def list_specialties(self) -> list[Specialty]: ...


class ProfessionalRepository(ABC):

    @abstractmethod
    async def save(self, professional: Professional) -> Professional:
        """Insere ou atualiza o profissional, incluindo a grade de horários."""

    @abstractmethod
    async def get_by_id(self, professional_id: uuid.UUID) -> Optional[Professional]: ...

    @abstractmethod
    async def get_by_registry(self, registry_number: str) -> Optional[Professional]: ...

    @abstractmethod
    async def search(self, filters: ProfessionalFilters) -> tuple[list[Professional], int]:
        """Retorna a página pedida e o total de registros que atendem aos filtros."""

    @abstractmethod
    async def get_names(self, professional_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]: ...

    @abstractmethod
    async def get_names_and_types(self, professional_ids: set[uuid.UUID]) -> dict[uuid.UUID, tuple[str, ProfessionalType]]: ...
