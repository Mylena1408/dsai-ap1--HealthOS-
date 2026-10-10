from enum import Enum
from typing import Optional, TypeVar
import uuid

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.medical_record_repository import (
    MedicalRecordRepository, PatientDirectoryRepository, PatientSearch,
)
from app.domain.entities.medical_record import (
    Allergy, AllergyCategory, AllergySeverity, AllergyStatus, BloodType, ClinicalEvolution, Condition,
    ConditionStatus, Diagnosis, DiagnosisCertainty, DiagnosisType, EmergencyContact, EvolutionStatus, PatientProfile,
    Procedure,
)
from app.domain.entities.patient import Patient
from app.infrastructure.persistence.models.medical_record_model import (
    AllergyModel, ClinicalEvolutionModel, ConditionModel, DiagnosisModel, EmergencyContactModel, PatientProfileModel,
    ProcedureModel,
)
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository

E = TypeVar("E")

# Campos persistidos de cada registro clínico e os Enums que precisam de conversão.
_ALLERGY = (["patient_id", "substance", "category", "severity", "reaction", "status", "recorded_at", "resolved_at"],
            {"category": AllergyCategory, "severity": AllergySeverity, "status": AllergyStatus})
_CONDITION = (["patient_id", "name", "code", "status", "onset_date", "resolved_date", "notes", "recorded_at"],
              {"status": ConditionStatus})
_DIAGNOSIS = (["patient_id", "professional_id", "appointment_id", "description", "code", "diagnosis_type",
               "certainty", "notes", "diagnosed_at"],
              {"diagnosis_type": DiagnosisType, "certainty": DiagnosisCertainty})
_PROCEDURE = (["patient_id", "professional_id", "appointment_id", "name", "performed_at", "notes"], {})
_EVOLUTION = (["patient_id", "professional_id", "appointment_id", "content", "status", "version", "created_at",
               "updated_at", "signed_at"], {"status": EvolutionStatus})


class SQLAlchemyPatientDirectoryRepository(PatientDirectoryRepository):

    def __init__(self, session: AsyncSession):
        self.session = session
        self._legacy = SQLAlchemyPatientRepository(session)

    async def search(self, search: PatientSearch) -> tuple[list[Patient], int]:
        conditions = []
        if search.query and search.query.strip():
            text = search.query.strip()
            clauses = [PatientModel.full_name.ilike(f"%{text}%"), PatientModel.email.ilike(f"%{text}%")]
            digits = "".join(c for c in text if c.isdigit())
            if digits:
                clauses.append(PatientModel.cpf.like(f"%{digits}%"))
            conditions.append(or_(*clauses))

        total = await self.session.scalar(select(func.count()).select_from(PatientModel).where(*conditions))
        order = desc(PatientModel.created_at) if search.order_by == "recent" else PatientModel.full_name
        result = await self.session.scalars(
            select(PatientModel).where(*conditions).order_by(order).limit(search.limit).offset(search.offset))
        return [self._legacy._map_to_domain(m) for m in result], total

    async def get(self, patient_id: uuid.UUID) -> Optional[Patient]:
        return await self._legacy.get_by_id(patient_id)


class SQLAlchemyMedicalRecordRepository(MedicalRecordRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    # ----------------------------------------------------------------- perfil

    async def get_profile(self, patient_id: uuid.UUID) -> Optional[PatientProfile]:
        model = await self.session.get(PatientProfileModel, patient_id)
        if not model:
            return None
        return PatientProfile(
            patient_id=model.patient_id, blood_type=BloodType(model.blood_type), occupation=model.occupation,
            notes=model.notes, updated_at=model.updated_at,
            emergency_contacts=[EmergencyContact(id=c.id, full_name=c.full_name, relationship=c.kinship,
                                                 phone=c.phone, is_primary=c.is_primary)
                                for c in model.emergency_contacts],
        )

    async def save_profile(self, profile: PatientProfile) -> PatientProfile:
        model = await self.session.get(PatientProfileModel, profile.patient_id)
        if model is None:
            model = PatientProfileModel(patient_id=profile.patient_id, emergency_contacts=[])
            self.session.add(model)
        model.blood_type = profile.blood_type.value
        model.occupation = profile.occupation
        model.notes = profile.notes
        model.updated_at = profile.updated_at

        # Sincroniza contatos: atualiza os existentes, cria os novos e remove os ausentes.
        existing = {c.id: c for c in model.emergency_contacts}
        synced = []
        for contact in profile.emergency_contacts:
            contact.id = contact.id or uuid.uuid4()
            row = existing.get(contact.id) or EmergencyContactModel(id=contact.id)
            row.full_name, row.kinship = contact.full_name, contact.relationship
            row.phone, row.is_primary = contact.phone, contact.is_primary
            synced.append(row)
        model.emergency_contacts = synced
        await self.session.flush()
        return profile

    # -------------------------------------------------------- registros clínicos

    async def list_allergies(self, patient_id):
        return await self._list(AllergyModel, Allergy, _ALLERGY, patient_id, desc(AllergyModel.recorded_at))

    async def get_allergy(self, allergy_id):
        return await self._get(AllergyModel, Allergy, _ALLERGY, allergy_id)

    async def save_allergy(self, allergy):
        return await self._upsert(AllergyModel, allergy, _ALLERGY)

    async def list_conditions(self, patient_id):
        return await self._list(ConditionModel, Condition, _CONDITION, patient_id, desc(ConditionModel.recorded_at))

    async def get_condition(self, condition_id):
        return await self._get(ConditionModel, Condition, _CONDITION, condition_id)

    async def save_condition(self, condition):
        return await self._upsert(ConditionModel, condition, _CONDITION)

    async def list_diagnoses(self, patient_id):
        return await self._list(DiagnosisModel, Diagnosis, _DIAGNOSIS, patient_id, desc(DiagnosisModel.diagnosed_at))

    async def get_diagnosis(self, diagnosis_id):
        return await self._get(DiagnosisModel, Diagnosis, _DIAGNOSIS, diagnosis_id)

    async def save_diagnosis(self, diagnosis):
        return await self._upsert(DiagnosisModel, diagnosis, _DIAGNOSIS)

    async def list_procedures(self, patient_id):
        return await self._list(ProcedureModel, Procedure, _PROCEDURE, patient_id, desc(ProcedureModel.performed_at))

    async def save_procedure(self, procedure):
        return await self._upsert(ProcedureModel, procedure, _PROCEDURE)

    async def list_evolutions(self, patient_id):
        return await self._list(ClinicalEvolutionModel, ClinicalEvolution, _EVOLUTION, patient_id,
                                desc(ClinicalEvolutionModel.created_at))

    async def get_evolution(self, evolution_id):
        return await self._get(ClinicalEvolutionModel, ClinicalEvolution, _EVOLUTION, evolution_id)

    async def save_evolution(self, evolution):
        return await self._upsert(ClinicalEvolutionModel, evolution, _EVOLUTION)

    # ------------------------------------------------------- mapeamento genérico

    async def _upsert(self, model_cls, entity: E, spec) -> E:
        fields, _ = spec
        model = await self.session.get(model_cls, entity.id) if entity.id else None
        if model is None:
            model = model_cls(id=entity.id or uuid.uuid4())
            self.session.add(model)
        for name in fields:
            value = getattr(entity, name)
            setattr(model, name, value.value if isinstance(value, Enum) else value)
        await self.session.flush()
        entity.id = model.id
        return entity

    async def _get(self, model_cls, entity_cls: type[E], spec, entity_id) -> Optional[E]:
        model = await self.session.get(model_cls, entity_id)
        return self._to_domain(entity_cls, model, spec) if model else None

    async def _list(self, model_cls, entity_cls: type[E], spec, patient_id, order) -> list[E]:
        result = await self.session.scalars(
            select(model_cls).where(model_cls.patient_id == patient_id).order_by(order))
        return [self._to_domain(entity_cls, m, spec) for m in result]

    @staticmethod
    def _to_domain(entity_cls: type[E], model, spec) -> E:
        fields, enums = spec
        values = {name: getattr(model, name) for name in fields}
        for name, enum_cls in enums.items():
            values[name] = enum_cls(values[name])
        return entity_cls(id=model.id, **values)
