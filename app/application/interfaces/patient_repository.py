from abc import ABC, abstractmethod
from typing import Optional, List
import uuid
from app.domain.entities.patient import Patient

class PatientRepository(ABC):
    """
    Interface de Repositório para Pacientes.
    Define as operações de persistência necessárias para a camada de aplicação.
    """

    @abstractmethod
    async def save(self, patient: Patient) -> Patient:
        """Persiste um novo paciente ou atualiza um existente."""
        pass

    @abstractmethod
    async def get_by_id(self, patient_id: uuid.UUID) -> Optional[Patient]:
        """Busca um paciente pelo seu ID único."""
        pass

    @abstractmethod
    async def get_by_cpf(self, cpf: str) -> Optional[Patient]:
        """Busca um paciente pelo seu CPF."""
        pass

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> List[Patient]:
        """Lista pacientes com paginação."""
        pass

    @abstractmethod
    async def update(self, patient: Patient) -> Patient:
        """Atualiza os dados de um paciente."""
        pass
