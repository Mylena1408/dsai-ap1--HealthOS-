"""Dados fictícios de sinais vitais e exames laboratoriais.

Cada paciente recebe um "perfil" (altura, peso, pressão de base) para que as
séries temporais sejam plausíveis. Os exames percorrem a máquina de estados com
horários coerentes; quem ainda "não chegou" a uma etapa fica parado no estado
correspondente, o que alimenta a fila do laboratório na demonstração.
"""
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.professional_repository import ProfessionalFilters
from app.domain.entities.laboratory import ExamPriority, ExamRequest, ExamType
from app.domain.entities.professional import ProfessionalType
from app.domain.entities.reference_range import ReferenceRange
from app.domain.entities.vital_signs import VitalSigns
from app.infrastructure.persistence.models.clinical_monitoring_model import ExamRequestModel, VitalSignsModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.repositories.sqlalchemy_clinical_monitoring_repository import (
    SQLAlchemyLaboratoryRepository, SQLAlchemyVitalSignsRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyProfessionalRepository,
)

if TYPE_CHECKING:
    from app.infrastructure.seed.demo_seed import SeedReport

INDICATIONS = ["Rotina anual (fictícia)", "Acompanhamento de condição crônica", "Avaliação pré-consulta",
               "Controle de tratamento", None]
# Até onde cada exame avança no fluxo (estado final desejado → peso no sorteio).
TARGET_STAGES = [("LIBERADO", 55), ("VALIDADO", 5), ("RESULTADO_REGISTRADO", 6), ("EM_PROCESSAMENTO", 5),
                 ("COLETADO", 4), ("AGENDADO", 8), ("SOLICITADO", 10), ("CANCELADO", 7)]
STAGE_ORDER = ["SOLICITADO", "AGENDADO", "COLETADO", "EM_PROCESSAMENTO", "RESULTADO_REGISTRADO", "VALIDADO", "LIBERADO"]


# ------------------------------------------------------------------ sinais vitais

async def seed_vital_signs(session: AsyncSession, rng: random.Random, report: "SeedReport", now: datetime) -> None:
    if await session.scalar(select(func.count()).select_from(VitalSignsModel)):
        report.add("vital_signs", created=False)
        return
    repo = SQLAlchemyVitalSignsRepository(session)
    for patient in (await session.scalars(select(PatientModel).order_by(PatientModel.cpf))).all():
        height = rng.randint(150, 190)
        weight = round(rng.uniform(19, 34) * (height / 100) ** 2, 1)
        systolic_base = rng.choice([110, 118, 125, 138, 150])
        moments = sorted(now - timedelta(days=rng.randint(1, 180), hours=rng.randint(0, 10))
                         for _ in range(rng.randint(3, 8)))
        for index, moment in enumerate(moments):
            weight = round(weight + rng.uniform(-1.2, 1.2), 1)
            systolic = systolic_base + rng.randint(-8, 12)
            await repo.save(VitalSigns(
                patient_id=patient.id, recorded_at=moment.replace(second=0, microsecond=0),
                systolic=systolic, diastolic=systolic - rng.randint(35, 50),
                heart_rate=rng.randint(58, 105), respiratory_rate=rng.randint(12, 22),
                temperature=round(rng.choice([36.4, 36.6, 36.8, 37.0, 37.9, 38.4]) + rng.uniform(-0.2, 0.2), 1),
                oxygen_saturation=rng.choice([99, 98, 97, 96, 95, 93]),
                weight_kg=weight, height_cm=height if index == 0 else None,
                glucose_mg_dl=rng.choice([None, None, rng.randint(75, 98), rng.randint(100, 180)]),
            ))
            report.add("vital_signs", created=True)


# -------------------------------------------------------------------- laboratório

def sample_value(reference: ReferenceRange, rng: random.Random, abnormal: bool) -> float:
    """Valor fictício dentro da faixa normal ou, se `abnormal`, um pouco fora dela."""
    low = reference.normal_min if reference.normal_min is not None else reference.normal_max * 0.55
    high = reference.normal_max if reference.normal_max is not None else reference.normal_min * 1.8
    if abnormal:
        sides = [s for s, bound in (("low", reference.normal_min), ("high", reference.normal_max)) if bound is not None]
        if rng.choice(sides) == "high":
            value = high * rng.uniform(1.05, 1.6)
        else:
            value = low * rng.uniform(0.55, 0.95)
    else:
        value = rng.uniform(low, high)
    return min(max(value, reference.plausible_min), reference.plausible_max)


async def seed_exam_requests(session: AsyncSession, total: int, rng: random.Random, report: "SeedReport",
                             now: datetime) -> None:
    if await session.scalar(select(func.count()).select_from(ExamRequestModel)):
        report.add("exam_requests", created=False)
        return
    repo = SQLAlchemyLaboratoryRepository(session)
    exam_types: list[ExamType] = await repo.list_exam_types()
    laboratories = await repo.list_laboratories()
    professionals, _ = await SQLAlchemyProfessionalRepository(session).search(ProfessionalFilters(limit=1000))
    doctors = [p for p in professionals if p.professional_type == ProfessionalType.DOCTOR] or professionals
    patient_ids = list((await session.scalars(select(PatientModel.id).order_by(PatientModel.cpf))).all())
    if not exam_types or not patient_ids or not doctors:
        return

    stages, weights = zip(*TARGET_STAGES)
    for _ in range(total):
        exam_type = rng.choice(exam_types)
        target = rng.choices(stages, weights)[0]
        requested_at = (now - timedelta(days=rng.randint(0, 120), hours=rng.randint(0, 12))).replace(
            second=0, microsecond=0)
        exam = ExamRequest(
            patient_id=rng.choice(patient_ids), exam_type_id=exam_type.id, requested_at=requested_at,
            requested_by=rng.choice(doctors).id, laboratory_id=rng.choice(laboratories).id if laboratories else None,
            priority=ExamPriority.URGENT if rng.random() < 0.15 else ExamPriority.ROUTINE,
            clinical_indication=rng.choice(INDICATIONS),
        )
        exam.register_creation()
        _advance(exam, exam_type, target, rng, now, validator=rng.choice(doctors).id)
        await repo.save_request(exam)
        report.add("exam_requests", created=True)


def _advance(exam: ExamRequest, exam_type: ExamType, target: str, rng: random.Random, now: datetime,
             validator) -> None:
    """Percorre o fluxo até `target`, sem nunca registrar um evento no futuro."""
    if target == "CANCELADO":
        exam.cancel("Solicitação cancelada (fictícia).", exam.requested_at + timedelta(hours=rng.randint(1, 48)))
        return
    goal = STAGE_ORDER.index(target)
    moment = exam.requested_at
    steps = []
    if goal >= 1 and rng.random() < 0.7:
        steps.append(("schedule", timedelta(hours=rng.randint(1, 6))))
    steps += [("collect", timedelta(days=rng.randint(0, 3), hours=rng.randint(1, 8))),
              ("process", timedelta(minutes=rng.randint(20, 120))),
              ("results", timedelta(hours=exam_type.turnaround_hours * rng.uniform(0.3, 1.0))),
              ("validate", timedelta(hours=rng.randint(1, 6))),
              ("release", timedelta(minutes=rng.randint(10, 90)))]
    stage_of = {"schedule": 1, "collect": 2, "process": 3, "results": 4, "validate": 5, "release": 6}
    abnormal = rng.random() < 0.3
    for step, delay in steps:
        if stage_of[step] > goal:
            break
        if step == "schedule":
            scheduled_for = moment + delay + timedelta(days=rng.randint(1, 3))
            if moment + delay >= now:
                break
            # Agendamentos de exames ainda não coletados apontam para o futuro.
            exam.schedule(max(scheduled_for, now + timedelta(hours=2)) if goal == 1 else scheduled_for,
                          moment + delay)
            moment = scheduled_for if goal > 1 else moment + delay
            continue
        moment += delay
        if moment >= now:
            break
        if step == "collect":
            exam.collect(moment)
        elif step == "process":
            exam.start_processing(moment)
        elif step == "results":
            values = {a.code: sample_value(a.reference, rng, abnormal and rng.random() < 0.6)
                      for a in exam_type.analytes}
            exam.record_results(exam_type, values, moment)
        elif step == "validate":
            exam.validate(validator, moment)
        elif step == "release":
            exam.release(moment)
