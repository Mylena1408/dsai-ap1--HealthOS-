from datetime import date, datetime, time, timedelta

import pytest

from app.application.dtos.appointment_dto import AppointmentCreateDTO
from app.application.dtos.patient_dto import PatientCreateDTO
from app.application.dtos.professional_dto import (
    DepartmentCreateDTO, ProfessionalCreateDTO, ProfessionalUpdateDTO, SpecialtyCreateDTO, WorkingHoursDTO,
)
from app.application.interfaces.appointment_repository import AppointmentFilters
from app.application.interfaces.professional_repository import ProfessionalFilters
from app.application.use_cases.appointment_use_case import AppointmentUseCase
from app.application.use_cases.manage_patient_use_case import ManagePatientUseCase
from app.application.use_cases.professional_use_case import ProfessionalUseCase
from app.domain.entities.appointment import AppointmentStatus as S
from app.domain.entities.professional import ProfessionalStatus, ProfessionalType
from app.domain.exceptions.common import (
    BusinessRuleViolation, ConflictError, EntityNotFoundError, InvalidTransitionError,
)
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.persistence.repositories.sqlalchemy_patient_repository import SQLAlchemyPatientRepository
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyCatalogRepository, SQLAlchemyProfessionalRepository,
)

MONDAY = datetime(2026, 11, 9, 7, 0)


class Clock:
    """Relógio controlável para testar regras que dependem do horário atual."""
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
async def ctx(db_session):
    clock = Clock(MONDAY)
    catalog = SQLAlchemyCatalogRepository(db_session)
    professionals = ProfessionalUseCase(SQLAlchemyProfessionalRepository(db_session), catalog)
    patients = ManagePatientUseCase(SQLAlchemyPatientRepository(db_session))
    appointments = AppointmentUseCase(
        SQLAlchemyAppointmentRepository(db_session), SQLAlchemyProfessionalRepository(db_session),
        catalog, SQLAlchemyPatientRepository(db_session), clock=clock,
    )

    department = await professionals.create_department(DepartmentCreateDTO(name="Clínica Médica"))
    specialty = await professionals.create_specialty(SpecialtyCreateDTO(name="Cardiologia", default_duration_minutes=40))
    doctor = await professionals.register(ProfessionalCreateDTO(
        full_name="Dr. João (fictício)", professional_type=ProfessionalType.DOCTOR,
        registry_number="CRM-PA 10001", department_id=department.id, specialty_id=specialty.id,
        working_hours=[WorkingHoursDTO(weekday=0, start_time=time(8), end_time=time(12))],
    ))
    maria = await patients.create_patient(PatientCreateDTO(
        full_name="Maria Silva", cpf="39053344705", birth_date=date(1990, 1, 1), gender="Feminino"))
    jose = await patients.create_patient(PatientCreateDTO(
        full_name="José Souza", cpf="52998224725", birth_date=date(1985, 5, 5), gender="Masculino"))
    return dict(clock=clock, professionals=professionals, appointments=appointments,
                doctor=doctor, specialty=specialty, maria=maria, jose=jose)


def booking(ctx, patient="maria", hour=9, minute=0, **extra):
    return AppointmentCreateDTO(patient_id=ctx[patient].id, professional_id=ctx["doctor"].id,
                                start_time=MONDAY.replace(hour=hour, minute=minute), **extra)


async def test_full_lifecycle(ctx):
    uc, clock = ctx["appointments"], ctx["clock"]
    appt = await uc.book(booking(ctx, reason="Check-up fictício"))
    assert appt.status == S.SCHEDULED
    assert appt.duration_minutes == 40  # herdado da especialidade
    assert appt.patient_name == "Maria Silva"
    assert appt.professional_name == "Dr. João (fictício)"
    assert appt.allowed_transitions == [S.CONFIRMED, S.CANCELLED]

    await uc.confirm(appt.id)
    clock.now = MONDAY.replace(hour=9)
    await uc.start(appt.id)
    clock.now = MONDAY.replace(hour=9, minute=40)
    done = await uc.complete(appt.id, "Orientações fictícias")

    assert done.status == S.COMPLETED
    assert [h.to_status for h in done.history] == [S.SCHEDULED, S.CONFIRMED, S.IN_PROGRESS, S.COMPLETED]
    with pytest.raises(InvalidTransitionError):
        await uc.cancel(appt.id, "não pode mais")


async def test_booking_rules(ctx):
    uc = ctx["appointments"]
    with pytest.raises(BusinessRuleViolation, match="expediente"):
        await uc.book(booking(ctx, hour=13))
    with pytest.raises(BusinessRuleViolation, match="futuro"):
        ctx["clock"].now = MONDAY.replace(hour=10)
        await uc.book(booking(ctx, hour=9))
    ctx["clock"].now = MONDAY

    await uc.book(booking(ctx, hour=9))
    with pytest.raises(ConflictError, match="profissional"):
        await uc.book(booking(ctx, patient="jose", hour=9, minute=20))

    other = await ctx["professionals"].register(ProfessionalCreateDTO(
        full_name="Enf. Carla (fictícia)", professional_type=ProfessionalType.NURSE,
        registry_number="COREN-PA 20002"))
    with pytest.raises(ConflictError, match="paciente"):
        await uc.book(AppointmentCreateDTO(patient_id=ctx["maria"].id, professional_id=other.id,
                                           start_time=MONDAY.replace(hour=9, minute=30), duration_minutes=30))


async def test_cancelled_slot_can_be_booked_again(ctx):
    uc = ctx["appointments"]
    first = await uc.book(booking(ctx, hour=10))
    await uc.cancel(first.id, "Paciente pediu para remarcar")
    second = await uc.book(booking(ctx, patient="jose", hour=10))
    assert second.status == S.SCHEDULED


async def test_reschedule_checks_conflicts(ctx):
    uc = ctx["appointments"]
    a = await uc.book(booking(ctx, hour=8))
    await uc.book(booking(ctx, patient="jose", hour=10))
    with pytest.raises(ConflictError):
        await uc.reschedule(a.id, MONDAY.replace(hour=10, minute=20))
    moved = await uc.reschedule(a.id, MONDAY.replace(hour=11))
    assert moved.start_time == MONDAY.replace(hour=11)


async def test_no_show_only_after_start(ctx):
    uc, clock = ctx["appointments"], ctx["clock"]
    appt = await uc.book(booking(ctx, hour=9))
    with pytest.raises(BusinessRuleViolation):
        await uc.mark_no_show(appt.id)
    clock.now = MONDAY.replace(hour=9, minute=15)
    assert (await uc.mark_no_show(appt.id)).status == S.NO_SHOW


async def test_available_slots_exclude_busy_and_past_times(ctx):
    uc, clock = ctx["appointments"], ctx["clock"]
    await uc.book(booking(ctx, hour=9, duration_minutes=30))
    clock.now = MONDAY.replace(hour=8, minute=10)

    slots = await uc.available_slots(ctx["doctor"].id, MONDAY, days=1, duration_minutes=30)
    starts = [s.start_time.time() for s in slots]
    assert time(8, 0) not in starts           # já passou
    assert time(9, 0) not in starts           # ocupado
    assert starts == [time(8, 30), time(9, 30), time(10), time(10, 30), time(11), time(11, 30)]

    tuesday = await uc.available_slots(ctx["doctor"].id, MONDAY + timedelta(days=1), days=1)
    assert tuesday == []  # sem expediente às terças


async def test_inactive_professional_cannot_receive_bookings(ctx):
    await ctx["professionals"].update(ctx["doctor"].id, ProfessionalUpdateDTO(status=ProfessionalStatus.ON_LEAVE))
    with pytest.raises(BusinessRuleViolation):
        await ctx["appointments"].book(booking(ctx))
    assert await ctx["appointments"].available_slots(ctx["doctor"].id, MONDAY) == []


async def test_search_and_not_found(ctx):
    uc = ctx["appointments"]
    await uc.book(booking(ctx, hour=8))
    second = await uc.book(booking(ctx, patient="jose", hour=10))
    await uc.cancel(second.id, "Motivo fictício")

    page = await uc.search(AppointmentFilters(statuses=[S.CANCELLED]))
    assert page.total == 1 and page.items[0].patient_name == "José Souza"
    page = await uc.search(AppointmentFilters(patient_id=ctx["maria"].id))
    assert page.total == 1

    found = await ctx["professionals"].search(ProfessionalFilters(query="joão"))
    assert found.total == 1 and found.items[0].specialty_name == "Cardiologia"

    with pytest.raises(EntityNotFoundError):
        await uc.confirm(ctx["maria"].id)  # id que não é de consulta


async def test_duplicate_registry_and_catalog_names(ctx):
    with pytest.raises(ConflictError):
        await ctx["professionals"].register(ProfessionalCreateDTO(
            full_name="Outro Nome", professional_type=ProfessionalType.DOCTOR, registry_number="CRM-PA 10001"))
    with pytest.raises(ConflictError):
        await ctx["professionals"].create_specialty(SpecialtyCreateDTO(name="cardiologia"))
