"""Dados fictícios de prontuário: perfil, contatos, alergias, condições, diagnósticos e procedimentos.

Os registros clínicos são criados com as entidades de domínio (que validam as
regras) e gravados pelo repositório, com datas retroativas coerentes: diagnósticos
e procedimentos ficam vinculados a consultas FINALIZADAS e datados no fim delas.
"""
import random
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.appointment import AppointmentStatus
from app.domain.entities.medical_record import (
    Allergy, AllergyCategory, AllergySeverity, BloodType, Condition, ConditionStatus, Diagnosis,
    DiagnosisCertainty, EmergencyContact, PatientProfile, Procedure,
)
from app.infrastructure.persistence.models.appointment_model import AppointmentModel
from app.infrastructure.persistence.models.medical_record_model import PatientProfileModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.repositories.sqlalchemy_medical_record_repository import (
    SQLAlchemyMedicalRecordRepository,
)
from app.infrastructure.seed.fake_data import (
    ALLERGENS, BLOOD_TYPES, CONDITIONS, DIAGNOSES, FIRST_NAMES, KINSHIPS, LAST_NAMES, OCCUPATIONS, PROCEDURES,
)

if TYPE_CHECKING:
    from app.infrastructure.seed.demo_seed import SeedReport


def _years_after(birth: date, years: int, rng: random.Random, today: date) -> date | None:
    """Data aleatória entre o aniversário de `years` anos e hoje (None se ainda não chegou)."""
    earliest = date(birth.year + years, birth.month, min(birth.day, 28))  # dia 28 evita 29/02 inexistente
    if earliest >= today:
        return None
    return earliest + timedelta(days=rng.randint(0, (today - earliest).days))


async def seed_medical_records(session: AsyncSession, rng: random.Random, report: "SeedReport", now: datetime) -> None:
    repo = SQLAlchemyMedicalRecordRepository(session)
    with_profile = set((await session.scalars(select(PatientProfileModel.patient_id))).all())
    patients = (await session.scalars(select(PatientModel).order_by(PatientModel.cpf))).all()

    completed = {}  # paciente -> consultas finalizadas (para diagnósticos e procedimentos)
    for appointment in await session.scalars(
            select(AppointmentModel).where(AppointmentModel.status == AppointmentStatus.COMPLETED.value)):
        completed.setdefault(appointment.patient_id, []).append(appointment)

    for patient in patients:
        # Perfil existente indica que o prontuário já foi gerado em uma execução anterior.
        if patient.id in with_profile:
            report.add("medical_records", created=False)
            continue
        await _seed_profile(repo, patient.id, rng, now)
        await _seed_allergies(repo, patient.id, rng, now)
        await _seed_conditions(repo, patient, rng, now)
        await _seed_from_appointments(repo, patient.id, completed.get(patient.id, []), rng, report)
        report.add("medical_records", created=True)


async def _seed_profile(repo, patient_id, rng, now) -> None:
    profile = PatientProfile(patient_id=patient_id, blood_type=BloodType(rng.choice(BLOOD_TYPES)),
                             occupation=rng.choice(OCCUPATIONS), updated_at=now)
    for _ in range(rng.choice([0, 1, 1, 2])):
        profile.add_contact(EmergencyContact(
            full_name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}", relationship=rng.choice(KINSHIPS),
            phone=f"(91) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"))
    await repo.save_profile(profile)


async def _seed_allergies(repo, patient_id, rng, now) -> None:
    for substance, category, severity, reaction in rng.sample(ALLERGENS, k=rng.choice([0, 0, 1, 1, 2])):
        await repo.save_allergy(Allergy(
            patient_id=patient_id, substance=substance, category=AllergyCategory(category),
            severity=AllergySeverity(severity), reaction=reaction,
            recorded_at=now - timedelta(days=rng.randint(30, 1500))))


async def _seed_conditions(repo, patient, rng, now) -> None:
    today = now.date()
    for name, code, min_age in rng.sample(CONDITIONS, k=rng.choice([0, 1, 1, 2, 3])):
        onset = _years_after(patient.birth_date, min_age, rng, today)
        if onset is None:
            continue  # paciente jovem demais para esta condição
        condition = Condition(patient_id=patient.id, name=name, code=code, onset_date=onset,
                              recorded_at=datetime.combine(onset, datetime.min.time()) + timedelta(days=1))
        roll = rng.random()
        if roll < 0.35:
            condition.change_status(ConditionStatus.CONTROLLED, today)
        elif roll < 0.5:
            condition.change_status(ConditionStatus.RESOLVED, min(today, onset + timedelta(days=rng.randint(30, 900))))
        await repo.save_condition(condition)


async def _seed_from_appointments(repo, patient_id, appointments, rng, report) -> None:
    for appointment in appointments:
        if rng.random() < 0.6:
            description, code = rng.choice(DIAGNOSES)
            diagnosis = Diagnosis(
                patient_id=patient_id, description=description, code=code,
                professional_id=appointment.professional_id, appointment_id=appointment.id,
                diagnosed_at=appointment.end_time)
            if rng.random() < 0.7:
                diagnosis.confirm()
            await repo.save_diagnosis(diagnosis)
            report.add("diagnoses", created=True)
        if rng.random() < 0.3:
            await repo.save_procedure(Procedure(
                patient_id=patient_id, name=rng.choice(PROCEDURES), performed_at=appointment.end_time,
                professional_id=appointment.professional_id, appointment_id=appointment.id))
            report.add("procedures", created=True)
