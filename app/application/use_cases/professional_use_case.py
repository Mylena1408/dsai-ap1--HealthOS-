import uuid

from app.application.dtos.common import Page
from app.application.dtos.professional_dto import (
    DepartmentCreateDTO, DepartmentResponseDTO, ProfessionalCreateDTO, ProfessionalResponseDTO,
    ProfessionalUpdateDTO, SpecialtyCreateDTO, SpecialtyResponseDTO, WorkingHoursDTO,
)
from app.application.interfaces.professional_repository import (
    CatalogRepository, ProfessionalFilters, ProfessionalRepository,
)
from app.domain.entities.professional import Department, Professional, Specialty, WorkingHours
from app.domain.exceptions.common import ConflictError, EntityNotFoundError


class ProfessionalUseCase:
    """Cadastro de profissionais de saúde, departamentos e especialidades."""

    def __init__(self, professional_repo: ProfessionalRepository, catalog_repo: CatalogRepository):
        self.professional_repo = professional_repo
        self.catalog_repo = catalog_repo

    # ----------------------------------------------------------- catálogos

    async def create_department(self, dto: DepartmentCreateDTO) -> DepartmentResponseDTO:
        if await self.catalog_repo.get_department_by_name(dto.name.strip()):
            raise ConflictError(f"Já existe um departamento chamado '{dto.name}'.")
        department = await self.catalog_repo.save_department(
            Department(name=dto.name.strip(), description=dto.description)
        )
        return DepartmentResponseDTO(**vars(department))

    async def list_departments(self) -> list[DepartmentResponseDTO]:
        return [DepartmentResponseDTO(**vars(d)) for d in await self.catalog_repo.list_departments()]

    async def create_specialty(self, dto: SpecialtyCreateDTO) -> SpecialtyResponseDTO:
        if await self.catalog_repo.get_specialty_by_name(dto.name.strip()):
            raise ConflictError(f"Já existe uma especialidade chamada '{dto.name}'.")
        specialty = await self.catalog_repo.save_specialty(Specialty(
            name=dto.name.strip(), description=dto.description,
            default_duration_minutes=dto.default_duration_minutes,
        ))
        return SpecialtyResponseDTO(**vars(specialty))

    async def list_specialties(self) -> list[SpecialtyResponseDTO]:
        return [SpecialtyResponseDTO(**vars(s)) for s in await self.catalog_repo.list_specialties()]

    # -------------------------------------------------------- profissionais

    async def register(self, dto: ProfessionalCreateDTO) -> ProfessionalResponseDTO:
        registry = dto.registry_number.strip()
        if await self.professional_repo.get_by_registry(registry):
            raise ConflictError(f"O registro profissional '{registry}' já está cadastrado.")
        await self._ensure_catalog_refs(dto.department_id, dto.specialty_id)

        professional = Professional(
            full_name=dto.full_name.strip(), professional_type=dto.professional_type,
            registry_number=registry, department_id=dto.department_id, specialty_id=dto.specialty_id,
            email=dto.email, phone=dto.phone, bio=dto.bio,
        )
        professional.set_working_hours([self._to_hours(h) for h in dto.working_hours])
        return await self._to_response(await self.professional_repo.save(professional))

    async def update(self, professional_id: uuid.UUID, dto: ProfessionalUpdateDTO) -> ProfessionalResponseDTO:
        professional = await self._get(professional_id)
        changes = dto.model_dump(exclude_unset=True)
        await self._ensure_catalog_refs(changes.get("department_id"), changes.get("specialty_id"))
        for attr, value in changes.items():
            setattr(professional, attr, value)
        professional.__post_init__()  # revalida as regras da entidade
        return await self._to_response(await self.professional_repo.save(professional))

    async def set_working_hours(self, professional_id: uuid.UUID,
                                hours: list[WorkingHoursDTO]) -> ProfessionalResponseDTO:
        professional = await self._get(professional_id)
        professional.set_working_hours([self._to_hours(h) for h in hours])
        return await self._to_response(await self.professional_repo.save(professional))

    async def get(self, professional_id: uuid.UUID) -> ProfessionalResponseDTO:
        return await self._to_response(await self._get(professional_id))

    async def search(self, filters: ProfessionalFilters) -> Page[ProfessionalResponseDTO]:
        items, total = await self.professional_repo.search(filters)
        departments = {d.id: d.name for d in await self.catalog_repo.list_departments()}
        specialties = {s.id: s.name for s in await self.catalog_repo.list_specialties()}
        return Page(
            items=[self._build_response(p, departments, specialties) for p in items],
            total=total, limit=filters.limit, offset=filters.offset,
        )

    # --------------------------------------------------------------- apoio

    async def _get(self, professional_id: uuid.UUID) -> Professional:
        professional = await self.professional_repo.get_by_id(professional_id)
        if not professional:
            raise EntityNotFoundError("Profissional", professional_id)
        return professional

    async def _ensure_catalog_refs(self, department_id, specialty_id) -> None:
        if department_id and not await self.catalog_repo.get_department(department_id):
            raise EntityNotFoundError("Departamento", department_id)
        if specialty_id and not await self.catalog_repo.get_specialty(specialty_id):
            raise EntityNotFoundError("Especialidade", specialty_id)

    @staticmethod
    def _to_hours(dto: WorkingHoursDTO) -> WorkingHours:
        return WorkingHours(weekday=dto.weekday, start_time=dto.start_time, end_time=dto.end_time)

    async def _to_response(self, professional: Professional) -> ProfessionalResponseDTO:
        department = (await self.catalog_repo.get_department(professional.department_id)
                      if professional.department_id else None)
        specialty = (await self.catalog_repo.get_specialty(professional.specialty_id)
                     if professional.specialty_id else None)
        return self._build_response(
            professional,
            {department.id: department.name} if department else {},
            {specialty.id: specialty.name} if specialty else {},
        )

    @staticmethod
    def _build_response(p: Professional, departments: dict, specialties: dict) -> ProfessionalResponseDTO:
        return ProfessionalResponseDTO(
            id=p.id, full_name=p.full_name, professional_type=p.professional_type,
            registry_number=p.registry_number,
            department_id=p.department_id, department_name=departments.get(p.department_id),
            specialty_id=p.specialty_id, specialty_name=specialties.get(p.specialty_id),
            email=p.email, phone=p.phone, status=p.status, bio=p.bio,
            working_hours=[WorkingHoursDTO(weekday=h.weekday, start_time=h.start_time, end_time=h.end_time)
                           for h in p.working_hours],
        )
