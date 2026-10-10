"""Compatibilidade de /clinical/notes com as evoluções clínicas.

As notas legadas apontam para 'users', que o sistema não cria para os profissionais.
Quando o ID informado é de um profissional, a nota é gravada como evolução
(tabela nova); caso contrário, segue o fluxo legado. Caminho e formato de
resposta não mudam (ADR-001).
"""
import uuid

from app.application.dtos.clinical_dto import ClinicalNoteCreateDTO, ClinicalNoteResponseDTO, ClinicalNoteUpdateDTO
from app.application.dtos.medical_record_dto import EvolutionCreateDTO, EvolutionDTO, EvolutionUpdateDTO
from app.application.use_cases.clinical_evolution_use_case import ClinicalEvolutionUseCase
from app.application.use_cases.medical_record_use_case import MedicalRecordUseCase
from app.domain.entities.medical_record import EvolutionStatus
from app.domain.exceptions.clinical_exceptions import NoteNotFoundError
from app.domain.exceptions.common import EntityNotFoundError

LEGACY_STATUS = {EvolutionStatus.DRAFT: "DRAFT", EvolutionStatus.SIGNED: "FINALIZED"}


def as_note(evolution: EvolutionDTO) -> ClinicalNoteResponseDTO:
    return ClinicalNoteResponseDTO(
        id=evolution.id, patient_id=evolution.patient_id, doctor_id=evolution.professional_id,
        content=evolution.content, timestamp=evolution.created_at, status=LEGACY_STATUS[evolution.status],
        version=evolution.version,
    )


class ClinicalNotesBridgeUseCase:

    def __init__(self, legacy: ClinicalEvolutionUseCase, records: MedicalRecordUseCase):
        self.legacy = legacy
        self.records = records

    async def create(self, dto: ClinicalNoteCreateDTO) -> ClinicalNoteResponseDTO:
        professional = await self.records.professional_repo.get_by_id(dto.doctor_id)
        if professional:
            return as_note(await self.records.add_evolution(
                dto.patient_id, EvolutionCreateDTO(professional_id=dto.doctor_id, content=dto.content), professional))
        return await self.legacy.create_note(dto)

    async def update(self, note_id: uuid.UUID, dto: ClinicalNoteUpdateDTO) -> ClinicalNoteResponseDTO:
        if await self._is_legacy(note_id):
            return await self.legacy.update_draft(note_id, dto)
        evolution = await self._evolution(note_id)
        return as_note(await self.records.update_evolution(
            evolution.patient_id, note_id, EvolutionUpdateDTO(content=dto.content)))

    async def finalize(self, note_id: uuid.UUID) -> ClinicalNoteResponseDTO:
        if await self._is_legacy(note_id):
            return await self.legacy.finalize_note(note_id)
        evolution = await self._evolution(note_id)
        return as_note(await self.records.sign_evolution(evolution.patient_id, note_id))

    async def history(self, patient_id: uuid.UUID) -> list[ClinicalNoteResponseDTO]:
        notes = await self.legacy.get_patient_history(patient_id)
        try:
            notes += [as_note(e) for e in await self.records.list_evolutions(patient_id)]
        except EntityNotFoundError:
            pass  # paciente inexistente: o legado responde só com as notas antigas (lista vazia)
        return sorted(notes, key=lambda n: n.timestamp, reverse=True)

    async def _is_legacy(self, note_id: uuid.UUID) -> bool:
        return await self.legacy.clinical_repository.get_by_id(note_id) is not None

    async def _evolution(self, note_id: uuid.UUID):
        evolution = await self.records.find_evolution(note_id)
        if not evolution:
            raise NoteNotFoundError("Nota não encontrada")
        return evolution
