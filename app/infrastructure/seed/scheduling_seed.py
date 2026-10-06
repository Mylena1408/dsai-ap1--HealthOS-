"""Dados fictícios de profissionais, catálogos e consultas.

Profissionais e catálogos passam pelo ProfessionalUseCase. As consultas são
montadas diretamente com a entidade Appointment e o repositório, porque o caso
de uso (corretamente) não permite agendar no passado; mesmo assim cada consulta
percorre as transições da máquina de estados com horários coerentes, então o
histórico gerado é o mesmo que a aplicação produziria.
"""
import random
from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.professional_dto import (
    DepartmentCreateDTO, ProfessionalCreateDTO, SpecialtyCreateDTO, WorkingHoursDTO,
)
from app.application.interfaces.professional_repository import ProfessionalFilters
from app.application.use_cases.professional_use_case import ProfessionalUseCase
from app.domain.entities.appointment import Appointment, AppointmentType
from app.domain.entities.professional import REGISTRY_COUNCIL, Professional, ProfessionalType
from app.infrastructure.persistence.models.appointment_model import AppointmentModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyCatalogRepository, SQLAlchemyProfessionalRepository,
)
from app.infrastructure.seed.fake_data import (
    APPOINTMENT_REASONS, DEPARTMENTS, PROFESSIONAL_MIX, SHIFTS, SPECIALTIES, fake_professional_name,
)

if TYPE_CHECKING:
    from app.infrastructure.seed.demo_seed import SeedReport

TITLES = {
    ProfessionalType.DOCTOR: "Dr(a).", ProfessionalType.NURSE: "Enf.", ProfessionalType.PHARMACIST: "Farm.",
    ProfessionalType.PHYSIOTHERAPIST: "Fisio.", ProfessionalType.PSYCHOLOGIST: "Psic.",
    ProfessionalType.NUTRITIONIST: "Nutri.", ProfessionalType.OTHER: "",
}
PAST_DAYS, FUTURE_DAYS = 30, 21


async def seed_catalog_and_professionals(session: AsyncSession, rng: random.Random, report: "SeedReport") -> None:
    catalog = SQLAlchemyCatalogRepository(session)
    use_case = ProfessionalUseCase(SQLAlchemyProfessionalRepository(session), catalog)

    departments = {}
    for name, description in DEPARTMENTS:
        existing = await catalog.get_department_by_name(name)
        departments[name] = existing or await use_case.create_department(
            DepartmentCreateDTO(name=name, description=description))
        report.add("departments", created=existing is None)

    specialties = {}
    for name, duration, department_name in SPECIALTIES:
        existing = await catalog.get_specialty_by_name(name)
        specialties[name] = (existing or await use_case.create_specialty(
            SpecialtyCreateDTO(name=name, default_duration_minutes=duration)), department_name)
        report.add("specialties", created=existing is None)

    sequence = 0
    for type_value, specialty_name, amount in PROFESSIONAL_MIX:
        professional_type = ProfessionalType(type_value)
        specialty, department_name = specialties[specialty_name]
        for _ in range(amount):
            sequence += 1
            # O nome é sorteado mesmo quando o registro já existe, para manter a sequência determinística.
            full_name = fake_professional_name(rng, TITLES[professional_type])
            shift = rng.choice(SHIFTS)
            weekdays = sorted(rng.sample(range(5), k=rng.randint(3, 5)))
            registry = f"{REGISTRY_COUNCIL[professional_type]}-PA {10000 + sequence} (fictício)"
            if await use_case.professional_repo.get_by_registry(registry):
                report.add("professionals", created=False)
                continue
            await use_case.register(ProfessionalCreateDTO(
                full_name=full_name, professional_type=professional_type, registry_number=registry,
                department_id=departments[department_name].id, specialty_id=specialty.id,
                email=f"profissional{sequence}@example.com",
                working_hours=[WorkingHoursDTO(weekday=d, start_time=time(shift[0]), end_time=time(shift[1]))
                               for d in weekdays],
            ))
            report.add("professionals", created=True)


async def seed_appointments(session: AsyncSession, total: int, rng: random.Random,
                            report: "SeedReport", now: datetime) -> None:
    # Consultas dependem do relógio; para manter a idempotência só são geradas em banco vazio.
    if await session.scalar(select(func.count()).select_from(AppointmentModel)):
        report.add("appointments", created=False)
        return

    professionals, _ = await SQLAlchemyProfessionalRepository(session).search(ProfessionalFilters(limit=1000))
    professionals = [p for p in professionals if p.working_hours]
    patient_ids = list((await session.scalars(select(PatientModel.id).order_by(PatientModel.cpf))).all())
    if not professionals or not patient_ids:
        return
    durations = {s.id: s.default_duration_minutes
                 for s in await SQLAlchemyCatalogRepository(session).list_specialties()}

    repo = SQLAlchemyAppointmentRepository(session)
    busy: dict = defaultdict(list)  # id do profissional ou do paciente -> [(início, fim)]
    created, attempts = 0, 0
    while created < total and attempts < total * 30:
        attempts += 1
        professional = rng.choice(professionals)
        duration = durations.get(professional.specialty_id, 30)
        start = _random_slot(professional, duration, now, rng)
        if start is None:
            continue
        end = start + timedelta(minutes=duration)
        patient_id = rng.choice(patient_ids)
        if start <= now < end or any(s < end and start < e for owner in (professional.id, patient_id)
                                     for s, e in busy[owner]):
            continue

        appointment = Appointment(
            patient_id=patient_id, professional_id=professional.id, start_time=start,
            duration_minutes=duration, specialty_id=professional.specialty_id,
            appointment_type=rng.choice(list(AppointmentType)), reason=rng.choice(APPOINTMENT_REASONS),
            created_at=min(start, now) - timedelta(days=rng.randint(3, 20)),
        )
        appointment.register_creation(appointment.created_at)
        _play_lifecycle(appointment, now, rng)
        await repo.save(appointment)
        busy[professional.id].append((start, end))
        busy[patient_id].append((start, end))
        created += 1
        report.add("appointments", created=True)


def _random_slot(professional: Professional, duration: int, now: datetime, rng: random.Random):
    day = (now + timedelta(days=rng.randint(-PAST_DAYS, FUTURE_DAYS))).date()
    windows = [w for w in professional.working_hours if w.weekday == day.weekday()]
    if not windows:
        return None
    window = rng.choice(windows)
    window_start = datetime.combine(day, window.start_time)
    slots = int((datetime.combine(day, window.end_time) - window_start).total_seconds() // 60 // duration)
    if slots < 1:
        return None
    return window_start + timedelta(minutes=duration * rng.randrange(slots))


def _play_lifecycle(appointment: Appointment, now: datetime, rng: random.Random) -> None:
    """Aplica transições plausíveis conforme a consulta esteja no passado ou no futuro."""
    start, end = appointment.start_time, appointment.end_time
    roll = rng.random()
    if end <= now:  # consulta já aconteceu (ou deveria ter acontecido)
        if roll < 0.70:
            appointment.confirm(start - timedelta(days=1))
            appointment.start(start)
            appointment.complete(end, notes="Atendimento fictício concluído.")
        elif roll < 0.85:
            appointment.mark_no_show(start + timedelta(minutes=15))
        else:
            appointment.cancel(start - timedelta(days=1), "Cancelada a pedido do paciente (fictício).")
    else:  # consulta futura
        decided_at = appointment.created_at + (now - appointment.created_at) / 2
        if roll < 0.45:
            appointment.confirm(decided_at)
        elif roll < 0.55:
            appointment.cancel(decided_at, "Conflito de agenda do paciente (fictício).")
