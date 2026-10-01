from abc import ABC, abstractmethod
from typing import Optional, List
import uuid
from app.domain.entities.clinical_note import ClinicalNote

class ClinicalRepository(ABC):
    """
    Interface de Repositório para o Prontuário Clínico.
    """

    @abstractmethod
    async def save(self, note: ClinicalNote) -> ClinicalNote:
        """Persiste uma nota clínica."""
        pass

    @abstractmethod
    async def get_by_id(self, note_id: uuid.UUID) -> Optional[ClinicalNote]:
        """Busca uma nota específica."""
        pass

    @abstractmethod
    async def list_by_patient(self, patient_id: uuid.UUID) -> List[ClinicalNote]:
        """Recupera todo o histórico de notas de um paciente em ordem cronológica."""
        pass

    @abstractmethod
    async def update(self, note: ClinicalNote) -> ClinicalNote:
        """Atualiza uma nota (apenas se estiver em rascunho)."""
        pass
