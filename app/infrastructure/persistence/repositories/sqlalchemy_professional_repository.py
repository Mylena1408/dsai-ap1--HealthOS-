from typing import Optional
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.professional_repository import (
    CatalogRepository, ProfessionalFilters, ProfessionalRepository,
)
from app.domain.entities.professional import (
    Department, Professional, ProfessionalStatus, ProfessionalType, Specialty, WorkingHours,
)
from app.infrastructure.persistence.models.professional_model import (
    DepartmentModel, ProfessionalModel, SpecialtyModel, WorkingHoursModel,
)


class SQLAlchemyCatalogRepository(CatalogRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_department(self, department: Department) -> Department:
        model = await self.session.get(DepartmentModel, department.id) if department.id else None
        if model is None:
            model = DepartmentModel(id=department.id or uuid.uuid4())
            self.session.add(model)
        model.name, model.description = department.name, department.description
        await self.session.flush()
        department.id = model.id
        return department

    async def get_department(self, department_id: uuid.UUID) -> Optional[Department]:
        model = await self.session.get(DepartmentModel, department_id)
        return self._department(model) if model else None

    async def get_department_by_name(self, name: str) -> Optional[Department]:
        model = await self.session.scalar(
            select(DepartmentModel).where(func.lower(DepartmentModel.name) == name.lower()))
        return self._department(model) if model else None

    async def list_departments(self) -> list[Department]:
        result = await self.session.scalars(select(DepartmentModel).order_by(DepartmentModel.name))
        return [self._department(m) for m in result]

    async def save_specialty(self, specialty: Specialty) -> Specialty:
        model = await self.session.get(SpecialtyModel, specialty.id) if specialty.id else None
        if model is None:
            model = SpecialtyModel(id=specialty.id or uuid.uuid4())
            self.session.add(model)
        model.name, model.description = specialty.name, specialty.description
        model.default_duration_minutes = specialty.default_duration_minutes
        await self.session.flush()
        specialty.id = model.id
        return specialty

    async def get_specialty(self, specialty_id: uuid.UUID) -> Optional[Specialty]:
        model = await self.session.get(SpecialtyModel, specialty_id)
        return self._specialty(model) if model else None

    async def get_specialty_by_name(self, name: str) -> Optional[Specialty]:
        model = await self.session.scalar(
            select(SpecialtyModel).where(func.lower(SpecialtyModel.name) == name.lower()))
        return self._specialty(model) if model else None

    async def list_specialties(self) -> list[Specialty]:
        result = await self.session.scalars(select(SpecialtyModel).order_by(SpecialtyModel.name))
        return [self._specialty(m) for m in result]

    @staticmethod
    def _department(m: DepartmentModel) -> Department:
        return Department(id=m.id, name=m.name, description=m.description)

    @staticmethod
    def _specialty(m: SpecialtyModel) -> Specialty:
        return Specialty(id=m.id, name=m.name, description=m.description,
                         default_duration_minutes=m.default_duration_minutes)


class SQLAlchemyProfessionalRepository(ProfessionalRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, professional: Professional) -> Professional:
        model = await self.session.get(ProfessionalModel, professional.id) if professional.id else None
        if model is None:
            model = ProfessionalModel(id=professional.id or uuid.uuid4(), working_hours=[])
            if professional.created_at:  # None explícito gravaria NULL em vez do default
                model.created_at = professional.created_at
            self.session.add(model)

        model.full_name = professional.full_name
        model.professional_type = professional.professional_type.value
        model.registry_number = professional.registry_number
        model.department_id = professional.department_id
        model.specialty_id = professional.specialty_id
        model.email = professional.email
        model.phone = professional.phone
        model.status = professional.status.value
        model.bio = professional.bio
        # A grade é substituída por inteiro; delete-orphan remove as janelas antigas.
        model.working_hours = [
            WorkingHoursModel(weekday=h.weekday, start_time=h.start_time, end_time=h.end_time)
            for h in professional.working_hours
        ]
        await self.session.flush()
        professional.id = model.id
        return professional

    async def get_by_id(self, professional_id: uuid.UUID) -> Optional[Professional]:
        model = await self.session.get(ProfessionalModel, professional_id)
        return self._to_domain(model) if model else None

    async def get_by_registry(self, registry_number: str) -> Optional[Professional]:
        model = await self.session.scalar(
            select(ProfessionalModel).where(ProfessionalModel.registry_number == registry_number))
        return self._to_domain(model) if model else None

    async def search(self, filters: ProfessionalFilters) -> tuple[list[Professional], int]:
        conditions = []
        if filters.query:
            pattern = f"%{filters.query.strip()}%"
            conditions.append(or_(ProfessionalModel.full_name.ilike(pattern),
                                  ProfessionalModel.registry_number.ilike(pattern)))
        if filters.professional_type:
            conditions.append(ProfessionalModel.professional_type == filters.professional_type.value)
        if filters.status:
            conditions.append(ProfessionalModel.status == filters.status.value)
        if filters.department_id:
            conditions.append(ProfessionalModel.department_id == filters.department_id)
        if filters.specialty_id:
            conditions.append(ProfessionalModel.specialty_id == filters.specialty_id)

        total = await self.session.scalar(select(func.count()).select_from(ProfessionalModel).where(*conditions))
        result = await self.session.scalars(
            select(ProfessionalModel).where(*conditions)
            .order_by(ProfessionalModel.full_name).limit(filters.limit).offset(filters.offset)
        )
        return [self._to_domain(m) for m in result], total

    async def get_names(self, professional_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not professional_ids:
            return {}
        rows = await self.session.execute(
            select(ProfessionalModel.id, ProfessionalModel.full_name)
            .where(ProfessionalModel.id.in_(professional_ids)))
        return dict(rows.all())

    @staticmethod
    def _to_domain(m: ProfessionalModel) -> Professional:
        return Professional(
            id=m.id, full_name=m.full_name, professional_type=ProfessionalType(m.professional_type),
            registry_number=m.registry_number, department_id=m.department_id, specialty_id=m.specialty_id,
            email=m.email, phone=m.phone, status=ProfessionalStatus(m.status), bio=m.bio,
            created_at=m.created_at,
            working_hours=[WorkingHours(id=h.id, professional_id=m.id, weekday=h.weekday,
                                        start_time=h.start_time, end_time=h.end_time)
                           for h in m.working_hours],
        )
