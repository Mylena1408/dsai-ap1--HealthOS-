from typing import Optional, List
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.domain.entities.patient import Patient
from app.application.interfaces.patient_repository import PatientRepository
from app.infrastructure.persistence.models.patient_model import PatientModel

class SQLAlchemyPatientRepository(PatientRepository):
    """
    Implementação concreta do PatientRepository utilizando SQLAlchemy e PostgreSQL.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, patient: Patient) -> Patient:
        db_patient = PatientModel(
            id=patient.id or uuid.uuid4(),
            full_name=patient.full_name,
            birth_date=patient.birth_date.date() if hasattr(patient.birth_date, 'date') else patient.birth_date,
            cpf=patient.cpf,
            gender=patient.gender,
            insurance_provider=patient.insurance_provider,
            insurance_number=patient.insurance_number,
            phone=patient.phone,
            email=patient.email,
            address=patient.address
        )
        self.session.add(db_patient)
        await self.session.flush()
        patient.id = db_patient.id
        return patient

    async def get_by_id(self, patient_id: uuid.UUID) -> Optional[Patient]:
        result = await self.session.execute(select(PatientModel).where(PatientModel.id == patient_id))
        db_patient = result.scalar_one_or_none()
        return self._map_to_domain(db_patient) if db_patient else None

    async def get_by_cpf(self, cpf: str) -> Optional[Patient]:
        result = await self.session.execute(select(PatientModel).where(PatientModel.cpf == cpf))
        db_patient = result.scalar_one_or_none()
        return self._map_to_domain(db_patient) if db_patient else None

    async def list_all(self, skip: int = 0, limit: int = 100) -> List[Patient]:
        result = await self.session.execute(select(PatientModel).offset(skip).limit(limit))
        db_patients = result.scalars().all()
        return [self._map_to_domain(p) for p in db_patients]

    async def update(self, patient: Patient) -> Patient:
        db_patient = await self.get_by_id(patient.id)
        if not db_patient:
            return None

        # Atualização simples via merge do modelo
        updated_model = PatientModel(
            id=patient.id,
            full_name=patient.full_name,
            birth_date=patient.birth_date.date() if hasattr(patient.birth_date, 'date') else patient.birth_date,
            cpf=patient.cpf,
            gender=patient.gender,
            insurance_provider=patient.insurance_provider,
            insurance_number=patient.insurance_number,
            phone=patient.phone,
            email=patient.email,
            address=patient.address
        )
        await self.session.merge(updated_model)
        await self.session.flush()
        return patient

    def _map_to_domain(self, db_patient: PatientModel) -> Patient:
        from app.domain.entities.patient import Patient # Evitar circular import
        return Patient(
            id=db_patient.id,
            full_name=db_patient.full_name,
            birth_date=db_patient.birth_date,
            cpf=db_patient.cpf,
            gender=db_patient.gender,
            insurance_provider=db_patient.insurance_provider,
            insurance_number=db_patient.insurance_number,
            phone=db_patient.phone,
            email=db_patient.email,
            address=db_patient.address
        )
