from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import uuid
from app.domain.exceptions.clinical_exceptions import NoteImmutableError

@dataclass
class ClinicalNote:
    """
    Entidade de Domínio ClinicalNote.
    Representa uma evolução clínica, anotação de consulta ou diagnóstico.
    """
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    content: str
    timestamp: datetime
    status: str = "DRAFT"  # DRAFT ou FINALIZED
    version: int = 1
    id: Optional[uuid.UUID] = None

    def finalize(self):
        """
        Finaliza a nota, tornando-a imutável.
        Uma vez finalizada, a nota não pode mais ser editada.
        """
        if self.status == "FINALIZED":
            raise NoteImmutableError(str(self.id))

        self.status = "FINALIZED"

    def update_content(self, new_content: str):
        """
        Atualiza o conteúdo da nota, apenas se ela estiver em rascunho.
        """
        if self.status == "FINALIZED":
            raise NoteImmutableError(str(self.id))

        self.content = new_content
        self.version += 1
