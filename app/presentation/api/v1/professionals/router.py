from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.common import Page
from app.application.dtos.professional_dto import (
    DepartmentCreateDTO, DepartmentResponseDTO, ProfessionalActivityDTO, ProfessionalCreateDTO, ProfessionalResponseDTO,
    ProfessionalUpdateDTO, SpecialtyCreateDTO, SpecialtyResponseDTO, WorkingHoursDTO,
)
from app.application.interfaces.professional_repository import ProfessionalFilters
from app.application.use_cases.professional_activity_use_case import ProfessionalActivityUseCase
from app.application.use_cases.professional_use_case import ProfessionalUseCase
from app.domain.entities.professional import ProfessionalStatus, ProfessionalType
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.sqlalchemy_professional_activity import (
    SQLAlchemyProfessionalActivity,
)
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyCatalogRepository, SQLAlchemyProfessionalRepository,
)

router = APIRouter(tags=["Profissionais de Saúde"])


async def get_use_case(session: AsyncSession = Depends(get_db)) -> ProfessionalUseCase:
    return ProfessionalUseCase(SQLAlchemyProfessionalRepository(session), SQLAlchemyCatalogRepository(session))


# ------------------------------------------------------------------ catálogos

@router.get("/departments", response_model=list[DepartmentResponseDTO])
async def list_departments(use_case: ProfessionalUseCase = Depends(get_use_case)):
    return await use_case.list_departments()


@router.post("/departments", response_model=DepartmentResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_department(request: DepartmentCreateDTO, use_case: ProfessionalUseCase = Depends(get_use_case)):
    return await use_case.create_department(request)


@router.get("/specialties", response_model=list[SpecialtyResponseDTO])
async def list_specialties(use_case: ProfessionalUseCase = Depends(get_use_case)):
    return await use_case.list_specialties()


@router.post("/specialties", response_model=SpecialtyResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_specialty(request: SpecialtyCreateDTO, use_case: ProfessionalUseCase = Depends(get_use_case)):
    return await use_case.create_specialty(request)


# -------------------------------------------------------------- profissionais

@router.get("/professionals", response_model=Page[ProfessionalResponseDTO])
async def search_professionals(
    q: Optional[str] = Query(None, max_length=100, description="Trecho do nome ou do registro"),
    professional_type: Optional[ProfessionalType] = None,
    status_: Optional[ProfessionalStatus] = Query(None, alias="status"),
    department_id: Optional[uuid.UUID] = None,
    specialty_id: Optional[uuid.UUID] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    use_case: ProfessionalUseCase = Depends(get_use_case),
):
    return await use_case.search(ProfessionalFilters(
        query=q, professional_type=professional_type, status=status_,
        department_id=department_id, specialty_id=specialty_id, limit=limit, offset=offset,
    ))


@router.post("/professionals", response_model=ProfessionalResponseDTO, status_code=status.HTTP_201_CREATED)
async def register_professional(request: ProfessionalCreateDTO, use_case: ProfessionalUseCase = Depends(get_use_case)):
    return await use_case.register(request)


@router.get("/professionals/{professional_id}", response_model=ProfessionalResponseDTO)
async def get_professional(professional_id: uuid.UUID, use_case: ProfessionalUseCase = Depends(get_use_case)):
    return await use_case.get(professional_id)


@router.get("/professionals/{professional_id}/activity", response_model=ProfessionalActivityDTO,
            summary="Histórico de atividades: consultas, sinais vitais, prescrições, dispensações e exames")
async def professional_activity(professional_id: uuid.UUID, limit: int = Query(20, ge=1, le=100),
                                session: AsyncSession = Depends(get_db),
                                use_case: ProfessionalUseCase = Depends(get_use_case)):
    return await ProfessionalActivityUseCase(use_case, SQLAlchemyProfessionalActivity(session)).activity(professional_id, limit)


@router.patch("/professionals/{professional_id}", response_model=ProfessionalResponseDTO)
async def update_professional(professional_id: uuid.UUID, request: ProfessionalUpdateDTO,
                              use_case: ProfessionalUseCase = Depends(get_use_case)):
    return await use_case.update(professional_id, request)


@router.put("/professionals/{professional_id}/working-hours", response_model=ProfessionalResponseDTO,
            summary="Substitui a grade semanal de atendimento")
async def set_working_hours(professional_id: uuid.UUID, request: list[WorkingHoursDTO],
                            use_case: ProfessionalUseCase = Depends(get_use_case)):
    return await use_case.set_working_hours(professional_id, request)
