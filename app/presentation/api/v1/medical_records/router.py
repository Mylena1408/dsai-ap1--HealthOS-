from datetime import date, datetime, time
from typing import Literal, Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.common import Page
from app.application.dtos.medical_record_dto import (
    AllergyCreateDTO, AllergyDTO, ConditionCreateDTO, ConditionDTO, ConditionStatusDTO, DiagnosisCreateDTO,
    DiagnosisDTO, EmergencyContactCreateDTO, MedicalRecordDTO, PatientListItemDTO, ProcedureCreateDTO, ProcedureDTO,
    ProfileDTO, ProfileUpdateDTO, TimelineEventDTO,
)
from app.application.interfaces.medical_record_repository import PatientSearch, TimelineQuery
from app.application.use_cases.medical_record_use_case import MedicalRecordUseCase
from app.domain.entities.timeline import TimelineEventType
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.persistence.repositories.sqlalchemy_medical_record_repository import (
    SQLAlchemyMedicalRecordRepository, SQLAlchemyPatientDirectoryRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_timeline_repository import SQLAlchemyTimelineRepository
from app.presentation.api.v1.appointments.router import get_use_case as get_appointment_use_case
from app.presentation.api.dependencies import get_events

router = APIRouter(prefix="/patients", tags=["Prontuário Eletrônico"])


async def get_use_case(session: AsyncSession = Depends(get_db), appointments=Depends(get_appointment_use_case),
                       events=Depends(get_events)) -> MedicalRecordUseCase:
    return MedicalRecordUseCase(
        SQLAlchemyMedicalRecordRepository(session), SQLAlchemyPatientDirectoryRepository(session),
        SQLAlchemyTimelineRepository(session), SQLAlchemyAppointmentRepository(session),
        appointments.professional_repo, appointments, events=events,
    )


UseCase = Depends(get_use_case)


@router.get("", response_model=Page[PatientListItemDTO], summary="Busca paginada de pacientes")
async def search_patients(
    q: Optional[str] = Query(None, max_length=100, description="Nome, CPF ou e-mail"),
    order_by: Literal["name", "recent"] = "name",
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
    use_case: MedicalRecordUseCase = UseCase,
):
    return await use_case.search_patients(PatientSearch(query=q, order_by=order_by, limit=limit, offset=offset))


@router.get("/{patient_id}/record", response_model=MedicalRecordDTO, summary="Resumo do prontuário")
async def get_record(patient_id: uuid.UUID, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.get_record(patient_id)


@router.get("/{patient_id}/timeline", response_model=Page[TimelineEventDTO])
async def get_timeline(
    patient_id: uuid.UUID,
    types: Optional[list[TimelineEventType]] = Query(None, description="Pode ser repetido; padrão: todos"),
    date_from: Optional[date] = None, date_to: Optional[date] = None,
    newest_first: bool = True,
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    use_case: MedicalRecordUseCase = UseCase,
):
    query = TimelineQuery(
        patient_id=patient_id, types=set(types) if types else set(TimelineEventType),
        date_from=datetime.combine(date_from, time.min) if date_from else None,
        date_to=datetime.combine(date_to, time.max) if date_to else None,
    )
    return await use_case.timeline(query, newest_first=newest_first, limit=limit, offset=offset)


# ------------------------------------------------------------ perfil e contatos

@router.put("/{patient_id}/profile", response_model=ProfileDTO)
async def update_profile(patient_id: uuid.UUID, request: ProfileUpdateDTO, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.update_profile(patient_id, request)


@router.post("/{patient_id}/emergency-contacts", response_model=ProfileDTO, status_code=status.HTTP_201_CREATED)
async def add_emergency_contact(patient_id: uuid.UUID, request: EmergencyContactCreateDTO,
                                use_case: MedicalRecordUseCase = UseCase):
    return await use_case.add_emergency_contact(patient_id, request)


@router.delete("/{patient_id}/emergency-contacts/{contact_id}", response_model=ProfileDTO)
async def remove_emergency_contact(patient_id: uuid.UUID, contact_id: uuid.UUID,
                                   use_case: MedicalRecordUseCase = UseCase):
    return await use_case.remove_emergency_contact(patient_id, contact_id)


# --------------------------------------------------------------------- alergias

@router.get("/{patient_id}/allergies", response_model=list[AllergyDTO])
async def list_allergies(patient_id: uuid.UUID, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.list_allergies(patient_id)


@router.post("/{patient_id}/allergies", response_model=AllergyDTO, status_code=status.HTTP_201_CREATED)
async def add_allergy(patient_id: uuid.UUID, request: AllergyCreateDTO, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.add_allergy(patient_id, request)


@router.post("/{patient_id}/allergies/{allergy_id}/resolve", response_model=AllergyDTO)
async def resolve_allergy(patient_id: uuid.UUID, allergy_id: uuid.UUID, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.resolve_allergy(patient_id, allergy_id)


# -------------------------------------------------------------------- condições

@router.get("/{patient_id}/conditions", response_model=list[ConditionDTO])
async def list_conditions(patient_id: uuid.UUID, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.list_conditions(patient_id)


@router.post("/{patient_id}/conditions", response_model=ConditionDTO, status_code=status.HTTP_201_CREATED)
async def add_condition(patient_id: uuid.UUID, request: ConditionCreateDTO, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.add_condition(patient_id, request)


@router.patch("/{patient_id}/conditions/{condition_id}/status", response_model=ConditionDTO)
async def change_condition_status(patient_id: uuid.UUID, condition_id: uuid.UUID, request: ConditionStatusDTO,
                                  use_case: MedicalRecordUseCase = UseCase):
    return await use_case.change_condition_status(patient_id, condition_id, request.status)


# ----------------------------------------------------------------- diagnósticos

@router.get("/{patient_id}/diagnoses", response_model=list[DiagnosisDTO])
async def list_diagnoses(patient_id: uuid.UUID, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.list_diagnoses(patient_id)


@router.post("/{patient_id}/diagnoses", response_model=DiagnosisDTO, status_code=status.HTTP_201_CREATED)
async def add_diagnosis(patient_id: uuid.UUID, request: DiagnosisCreateDTO, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.add_diagnosis(patient_id, request)


@router.post("/{patient_id}/diagnoses/{diagnosis_id}/confirm", response_model=DiagnosisDTO)
async def confirm_diagnosis(patient_id: uuid.UUID, diagnosis_id: uuid.UUID, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.confirm_diagnosis(patient_id, diagnosis_id)


@router.post("/{patient_id}/diagnoses/{diagnosis_id}/rule-out", response_model=DiagnosisDTO)
async def rule_out_diagnosis(patient_id: uuid.UUID, diagnosis_id: uuid.UUID, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.rule_out_diagnosis(patient_id, diagnosis_id)


# ---------------------------------------------------------------- procedimentos

@router.get("/{patient_id}/procedures", response_model=list[ProcedureDTO])
async def list_procedures(patient_id: uuid.UUID, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.list_procedures(patient_id)


@router.post("/{patient_id}/procedures", response_model=ProcedureDTO, status_code=status.HTTP_201_CREATED)
async def add_procedure(patient_id: uuid.UUID, request: ProcedureCreateDTO, use_case: MedicalRecordUseCase = UseCase):
    return await use_case.add_procedure(patient_id, request)
