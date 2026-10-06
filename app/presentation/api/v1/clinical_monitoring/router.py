from datetime import date, datetime, time
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.clinical_monitoring_dto import (
    AnalyteHistoryDTO, ExamRequestCreateDTO, ExamRequestDTO, ExamResultsInputDTO, ExamScheduleDTO, ExamTypeDTO,
    ExamValidateDTO, LaboratoryDTO, ReasonDTO, VitalSignsCreateDTO, VitalSignsDTO, VitalSignsSummaryDTO,
)
from app.application.dtos.common import Page
from app.application.interfaces.clinical_monitoring_repository import ExamRequestFilters
from app.application.use_cases.laboratory_use_case import LaboratoryUseCase
from app.application.use_cases.vital_signs_use_case import VitalSignsUseCase
from app.domain.entities.laboratory import ExamPriority, ExamStatus
from app.infrastructure.persistence.database import get_db
from app.presentation.api.dependencies import get_events
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.persistence.repositories.sqlalchemy_clinical_monitoring_repository import (
    SQLAlchemyLaboratoryRepository, SQLAlchemyVitalSignsRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_medical_record_repository import (
    SQLAlchemyPatientDirectoryRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyProfessionalRepository,
)

router = APIRouter()


async def get_vitals(session: AsyncSession = Depends(get_db), events=Depends(get_events)) -> VitalSignsUseCase:
    return VitalSignsUseCase(SQLAlchemyVitalSignsRepository(session), SQLAlchemyPatientDirectoryRepository(session),
                             SQLAlchemyProfessionalRepository(session), events=events)


async def get_lab(session: AsyncSession = Depends(get_db), events=Depends(get_events)) -> LaboratoryUseCase:
    return LaboratoryUseCase(SQLAlchemyLaboratoryRepository(session), SQLAlchemyPatientDirectoryRepository(session),
                             SQLAlchemyProfessionalRepository(session), SQLAlchemyAppointmentRepository(session),
                             events=events)


Vitals = Depends(get_vitals)
Lab = Depends(get_lab)


def _day_start(value: Optional[date]) -> Optional[datetime]:
    return datetime.combine(value, time.min) if value else None


def _day_end(value: Optional[date]) -> Optional[datetime]:
    return datetime.combine(value, time.max) if value else None


# ------------------------------------------------------------------ sinais vitais

@router.post("/patients/{patient_id}/vital-signs", response_model=VitalSignsDTO,
             status_code=status.HTTP_201_CREATED, tags=["Sinais Vitais"])
async def record_vital_signs(patient_id: uuid.UUID, request: VitalSignsCreateDTO, use_case: VitalSignsUseCase = Vitals):
    return await use_case.record(patient_id, request)


@router.get("/patients/{patient_id}/vital-signs", response_model=Page[VitalSignsDTO], tags=["Sinais Vitais"])
async def list_vital_signs(patient_id: uuid.UUID, date_from: Optional[date] = None, date_to: Optional[date] = None,
                           limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0),
                           use_case: VitalSignsUseCase = Vitals):
    return await use_case.page(patient_id, _day_start(date_from), _day_end(date_to), limit, offset)


@router.get("/patients/{patient_id}/vital-signs/summary", response_model=VitalSignsSummaryDTO, tags=["Sinais Vitais"],
            summary="Última medida, tendência e série temporal de cada métrica")
async def vital_signs_summary(patient_id: uuid.UUID, use_case: VitalSignsUseCase = Vitals):
    return await use_case.summary(patient_id)


# -------------------------------------------------------------------- laboratório

@router.get("/exam-types", response_model=list[ExamTypeDTO], tags=["Laboratório"])
async def list_exam_types(use_case: LaboratoryUseCase = Lab):
    return await use_case.exam_types()


@router.get("/laboratories", response_model=list[LaboratoryDTO], tags=["Laboratório"])
async def list_laboratories(use_case: LaboratoryUseCase = Lab):
    return await use_case.laboratories()


@router.get("/exam-requests", response_model=Page[ExamRequestDTO], tags=["Laboratório"])
async def search_exam_requests(
    patient_id: Optional[uuid.UUID] = None,
    status_: Optional[list[ExamStatus]] = Query(None, alias="status", description="Pode ser repetido"),
    exam_type_id: Optional[uuid.UUID] = None, priority: Optional[ExamPriority] = None,
    date_from: Optional[date] = None, date_to: Optional[date] = None,
    only_abnormal: bool = False, newest_first: bool = True,
    limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0),
    use_case: LaboratoryUseCase = Lab,
):
    return await use_case.search(ExamRequestFilters(
        patient_id=patient_id, statuses=status_ or [], exam_type_id=exam_type_id, priority=priority,
        date_from=_day_start(date_from), date_to=_day_end(date_to), only_abnormal=only_abnormal,
        newest_first=newest_first, limit=limit, offset=offset,
    ))


@router.post("/exam-requests", response_model=ExamRequestDTO, status_code=status.HTTP_201_CREATED, tags=["Laboratório"])
async def request_exam(request: ExamRequestCreateDTO, use_case: LaboratoryUseCase = Lab):
    return await use_case.request(request)


@router.get("/exam-requests/{request_id}", response_model=ExamRequestDTO, tags=["Laboratório"])
async def get_exam_request(request_id: uuid.UUID, use_case: LaboratoryUseCase = Lab):
    return await use_case.get(request_id)


@router.post("/exam-requests/{request_id}/schedule", response_model=ExamRequestDTO, tags=["Laboratório"])
async def schedule_collection(request_id: uuid.UUID, request: ExamScheduleDTO, use_case: LaboratoryUseCase = Lab):
    return await use_case.schedule(request_id, request.scheduled_for)


@router.post("/exam-requests/{request_id}/collect", response_model=ExamRequestDTO, tags=["Laboratório"])
async def collect_sample(request_id: uuid.UUID, use_case: LaboratoryUseCase = Lab):
    return await use_case.collect(request_id)


@router.post("/exam-requests/{request_id}/start-processing", response_model=ExamRequestDTO, tags=["Laboratório"])
async def start_processing(request_id: uuid.UUID, use_case: LaboratoryUseCase = Lab):
    return await use_case.start_processing(request_id)


@router.post("/exam-requests/{request_id}/results", response_model=ExamRequestDTO, tags=["Laboratório"])
async def record_results(request_id: uuid.UUID, request: ExamResultsInputDTO, use_case: LaboratoryUseCase = Lab):
    return await use_case.record_results(request_id, request.values, request.notes)


@router.post("/exam-requests/{request_id}/validate", response_model=ExamRequestDTO, tags=["Laboratório"])
async def validate_results(request_id: uuid.UUID, request: ExamValidateDTO, use_case: LaboratoryUseCase = Lab):
    return await use_case.validate(request_id, request.professional_id)


@router.post("/exam-requests/{request_id}/return", response_model=ExamRequestDTO, tags=["Laboratório"],
             summary="Devolve o laudo para correção")
async def return_for_correction(request_id: uuid.UUID, request: ReasonDTO, use_case: LaboratoryUseCase = Lab):
    return await use_case.return_for_correction(request_id, request.reason)


@router.post("/exam-requests/{request_id}/release", response_model=ExamRequestDTO, tags=["Laboratório"])
async def release_results(request_id: uuid.UUID, use_case: LaboratoryUseCase = Lab):
    return await use_case.release(request_id)


@router.post("/exam-requests/{request_id}/cancel", response_model=ExamRequestDTO, tags=["Laboratório"])
async def cancel_exam(request_id: uuid.UUID, request: ReasonDTO, use_case: LaboratoryUseCase = Lab):
    return await use_case.cancel(request_id, request.reason)


@router.get("/patients/{patient_id}/exams/analytes/{analyte_code}/history", response_model=AnalyteHistoryDTO,
            tags=["Laboratório"], summary="Evolução de um analito nos resultados liberados")
async def analyte_history(patient_id: uuid.UUID, analyte_code: str, use_case: LaboratoryUseCase = Lab):
    return await use_case.analyte_history(patient_id, analyte_code)
