from typing import List
import uuid
from datetime import datetime
from app.application.interfaces.clinical_repository import ClinicalRepository
from app.application.dtos.clinical_dto import ClinicalNoteCreateDTO, ClinicalNoteUpdateDTO, ClinicalNoteResponseDTO
from app.domain.entities.clinical_note import ClinicalNote
from app.domain.exceptions.clinical_exceptions import NoteImmutableError, NoteNotFoundError

class ClinicalEvolutionUseCase:
    """
    Caso de Uso para a evolução clínica de pacientes.
    Gerencia a criação, finalização e visualização de notas médicas.
    """

    def __init__(self, clinical_repository: ClinicalRepository):
        self.clinical_repository = clinical_repository

    async def create_note(self, request: ClinicalNoteCreateDTO) -> ClinicalNoteResponseDTO:
        # 1. Criação da Entidade de Domínio (Inicia como DRAFT)
        note = ClinicalNote(
            patient_id=request.patient_id,
            doctor_id=request.doctor_id,
            content=request.content,
            timestamp=datetime.now(),
            status="DRAFT"
        )

        # 2. Persistência
        created_note = await self.clinical_repository.save(note)

        # 3. Retorno via DTO
        return ClinicalNoteResponseDTO(
            id=created_note.id,
            patient_id=created_note.patient_id,
            doctor_id=created_note.doctor_id,
            content=created_note.content,
            timestamp=created_note.timestamp,
            status=created_note.status,
            version=created_note.version
        )

    async def get_patient_history(self, patient_id: uuid.UUID) -> List[ClinicalNoteResponseDTO]:
        notes = await self.clinical_repository.list_by_patient(patient_id)
        return [
            ClinicalNoteResponseDTO(
                id=n.id,
                patient_id=n.patient_id,
                doctor_id=n.doctor_id,
                content=n.content,
                timestamp=n.timestamp,
                status=n.status,
                version=n.version
            ) for n in notes
        ]

    async def finalize_note(self, note_id: uuid.UUID) -> ClinicalNoteResponseDTO:
        # 1. Busca a nota
        note = await self.clinical_repository.get_by_id(note_id)
        if not note:
            raise NoteNotFoundError()

        # 2. Aplica a regra de negócio de imutabilidade do Domínio
        note.finalize()

        # 3. Persiste a alteração de status
        finalized_note = await self.clinical_repository.update(note)

        return ClinicalNoteResponseDTO(
            id=finalized_note.id,
            patient_id=finalized_note.patient_id,
            doctor_id=finalized_note.doctor_id,
            content=finalized_note.content,
            timestamp=finalized_note.timestamp,
            status=finalized_note.status,
            version=finalized_note.version
        )

    async def update_draft(self, note_id: uuid.UUID, request: ClinicalNoteUpdateDTO) -> ClinicalNoteResponseDTO:
        # 1. Busca a nota
        note = await self.clinical_// la la lala
        # Note: I will fix the typo and complete the logic
        note = await self.clinical_repository.get_by_id(note_id)
        if not note:
            raise NoteNotFoundError()

        # 2. Tenta atualizar o conteúdo (o domínio lançará NoteImmutableError se for FINALIZED)
        note.update_content(request.content)

        # 3. Persiste
        updated_note = await self.clinical_repository.update(note)

        return ClinicalNoteResponseDTO(
            id=updated_note.id,
            patient_id=updated_note.patient_id,
            doctor_id=updated_note.doctor_id,
            content=updated_note.content,
            timestamp=updated_note.timestamp,
            status=updated_note.status,
            version=updated_note.version
        )
