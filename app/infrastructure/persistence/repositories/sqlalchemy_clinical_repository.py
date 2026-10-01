from typing import Optional, List
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.domain.entities.clinical_note import ClinicalNote
from app.application.interfaces.clinical_repository import ClinicalRepository
from app.infrastructure.persistence.models.clinical_model import ClinicalNoteModel

class SQLAlchemyClinicalRepository(ClinicalRepository):
    """
    Implementação concreta do ClinicalRepository utilizando SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, note: ClinicalNote) -> ClinicalNote:
        db_note = ClinicalNoteModel(
            id=note.id or uuid.uuid4(),
            patient_id=note.patient_id,
            doctor_id=note.doctor_id,
            content=note.content,
            timestamp=note.timestamp,
            status=note.status,
            version=note.version
        )
        self.session.add(db_note)
        await self.session.flush()
        note.id = db_note.id
        return note

    async def get_by_id(self, note_id: uuid.UUID) -> Optional[ClinicalNote]:
        result = await self.session.execute(select(ClinicalNoteModel).where(ClinicalNoteModel.id == note_id))
        db_note = result.scalar_one_or_none()
        return self._map_to_domain(db_note) if db_note else None

    async def list_by_patient(self, patient_id: uuid.UUID) -> List[ClinicalNote]:
        # Busca as notas do paciente ordenadas pela data mais recente
        stmt = select(ClinicalNoteModel).where(ClinicalNoteModel.patient_id == patient_id).order_by(desc(ClinicalNoteModel.timestamp))
        result = await self.session.execute(stmt)
        db_notes = result.scalars().all()
        return [self._map_to_domain(n) for n in db_notes]

    async def update(self, note: ClinicalNote) -> ClinicalNote:
        # Como a imutabilidade é controlada no Domínio, aqui apenas persistimos
        db_note = await self.get_by_id(note.id)
        if not db_note:
            return None

        # Atualizamos o modelo de banco
        # Nota: Em uma implementação real, usaríamos session.merge() ou atualizaríamos os campos individualmente
        updated_model = ClinicalNoteModel(
            id=note.id,
            patient_id=note.patient_id,
            doctor_id=note.doctor_id,
            content=note.content,
            timestamp=note.timestamp,
            status=note.status,
            version=note.version
        )
        await self.session.merge(updated_model)
        await self.session.flush()
        return note

    def _map_to_domain(self, db_note: ClinicalNoteModel) -> ClinicalNote:
        return ClinicalNote(
            id=db_note.id,
            patient_id=db_note.patient_id,
            doctor_id=db_note.doctor_id,
            content=db_note.content,
            timestamp=db_note.timestamp,
            status=db_note.status,
            version=db_note.version
        )
