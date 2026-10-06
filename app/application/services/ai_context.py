"""Monta o contexto mínimo do paciente para a IA a partir dos casos de uso existentes.

Minimização de dados: apenas primeiro nome, idade e fatos clínicos. CPF, e-mail,
telefone, endereço e convênio nunca entram no contexto.
"""
from dataclasses import dataclass
import uuid

from app.application.interfaces.clinical_monitoring_repository import ExamRequestFilters
from app.application.use_cases.dashboard_use_case import DashboardUseCase
from app.application.use_cases.laboratory_use_case import LaboratoryUseCase
from app.application.use_cases.medical_record_use_case import MedicalRecordUseCase
from app.application.use_cases.prescription_use_case import PrescriptionUseCase
from app.application.use_cases.vital_signs_use_case import VitalSignsUseCase
from app.domain.entities.assistant import ContextFact, PatientContext
from app.domain.entities.laboratory import ExamStatus
from app.domain.entities.pharmacy import ItemStatus

RECENT_EXAMS = 5
FLAG_TEXT = {"NORMAL": "normal", "BAIXO": "baixo", "ALTO": "alto",
             "CRITICO_BAIXO": "crítico (baixo)", "CRITICO_ALTO": "crítico (alto)"}


def describe_exam(exam) -> str:
    """Uma linha por analito: 'Nome: valor unidade (ref. ...) FLAG' — usada também pela IA demo."""
    return "\n".join(f"{r.analyte_name}: {r.value:g} {r.unit} (ref. {r.reference_text}) {r.flag.value}"
                     for r in exam.results)


@dataclass
class ContextSources:
    records: MedicalRecordUseCase
    vitals: VitalSignsUseCase
    laboratory: LaboratoryUseCase
    prescriptions: PrescriptionUseCase
    dashboards: DashboardUseCase


class PatientContextBuilder:

    def __init__(self, sources: ContextSources):
        self.s = sources

    async def build(self, patient_id: uuid.UUID) -> PatientContext:
        record = await self.s.records.get_record(patient_id)  # 404 se o paciente não existir
        facts: list[ContextFact] = []

        facts += [ContextFact("Alergia", f"{a.substance} ({a.severity.value.lower()})"
                              + (f": {a.reaction}" if a.reaction else "")) for a in record.active_allergies]
        facts += [ContextFact("Condição", f"{c.name} — {c.status.value.lower()}"
                              + (f", desde {c.onset_date:%m/%Y}" if c.onset_date else "")) for c in record.active_conditions]
        facts += [ContextFact("Condição", f"Diagnóstico registrado ({d.certainty.value.lower()}): {d.description}")
                  for d in record.recent_diagnoses]

        for m in await self.s.prescriptions.patient_medications(patient_id, ItemStatus.IN_USE):
            facts.append(ContextFact("Medicamento", f"{m.medication_name} — {m.dose}, {m.frequency}"))

        exams = await self.s.laboratory.search(ExamRequestFilters(
            patient_id=patient_id, statuses=[ExamStatus.RELEASED], limit=RECENT_EXAMS))
        for e in exams.items:
            abnormal = [f"{r.analyte_name} {r.value:g} {r.unit} ({FLAG_TEXT[r.flag.value]})"
                        for r in e.results if r.flag.value != "NORMAL"]
            when = f"{e.released_at:%d/%m/%Y}" if e.released_at else ""
            facts.append(ContextFact("Exame", f"{e.exam_name} em {when}: " + (
                "fora da referência — " + "; ".join(abnormal) if abnormal else "dentro da referência")))

        summary = await self.s.vitals.summary(patient_id)
        for metric in summary.metrics:
            if metric.metric.value == "height_cm":
                continue
            state = "" if metric.flag is None else (" — alterado" if metric.flag.value != "NORMAL" else " — normal")
            facts.append(ContextFact("Sinal vital", f"{metric.label}: {metric.latest:g} {metric.unit}"
                                     f" em {metric.latest_at:%d/%m/%Y}{state}"))

        if record.last_appointment:
            a = record.last_appointment
            facts.append(ContextFact("Consulta", f"Última consulta: {a.start_time:%d/%m/%Y} com {a.professional_name}"))
        for a in record.upcoming_appointments:
            facts.append(ContextFact("Consulta", f"Próxima consulta: {a.start_time:%d/%m/%Y %H:%M} com {a.professional_name}"))

        score = await self.s.dashboards.health_score(patient_id)
        if score.score is not None:
            facts.append(ContextFact("Health Score", f"Health Score (indicador demonstrativo): {score.score}/100 — "
                                     + "; ".join(f"{c.label} {c.score}" for c in score.components if c.applicable)))

        return PatientContext(patient_id=patient_id, first_name=record.patient.full_name.split()[0],
                              age=record.age, facts=facts)

    async def exam(self, exam_id: uuid.UUID):
        return await self.s.laboratory.get(exam_id)
