"""Linha do tempo do paciente, montada a partir das tabelas de cada módulo.

Cada fonte é consultada só quando o tipo de evento foi pedido. O volume por
paciente é pequeno em um sistema didático, então os eventos são ordenados e
paginados em memória pelo caso de uso (ADR-009).
"""
from datetime import datetime, time
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.medical_record_repository import TimelineQuery, TimelineRepository
from app.domain.entities.appointment import AppointmentType
from app.domain.entities.timeline import TimelineEvent, TimelineEventType as T
from app.domain.entities.triage import TriagePriority
from app.infrastructure.persistence.models.alert_model import PatientAlertModel
from app.infrastructure.persistence.models.appointment_model import AppointmentModel
from app.infrastructure.persistence.models.clinical_model import ClinicalNoteModel
from app.infrastructure.persistence.models.medical_record_model import (
    AllergyModel, ConditionModel, DiagnosisModel, ProcedureModel,
)
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.models.professional_model import ProfessionalModel
from app.infrastructure.persistence.models.triage_model import TriageModel

APPOINTMENT_TYPE_LABELS = {
    AppointmentType.FIRST_VISIT.value: "Primeira consulta", AppointmentType.FOLLOW_UP.value: "Retorno",
    AppointmentType.URGENT.value: "Urgência", AppointmentType.TELEMEDICINE.value: "Teleconsulta",
}
NOTE_PREVIEW = 200


def _preview(text: Optional[str]) -> Optional[str]:
    if text and len(text) > NOTE_PREVIEW:
        return text[:NOTE_PREVIEW].rstrip() + "…"
    return text


class SQLAlchemyTimelineRepository(TimelineRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def collect(self, query: TimelineQuery) -> list[TimelineEvent]:
        sources = {
            T.REGISTRATION: self._registration, T.APPOINTMENT: self._appointments,
            T.CLINICAL_NOTE: self._notes, T.ALERT: self._alerts, T.TRIAGE: self._triages,
            T.ALLERGY: self._allergies, T.CONDITION: self._conditions,
            T.DIAGNOSIS: self._diagnoses, T.PROCEDURE: self._procedures,
        }
        events: list[TimelineEvent] = []
        for event_type in query.types:
            events.extend(await sources[event_type](query.patient_id))
        return [e for e in events if self._in_range(e.occurred_at, query)]

    @staticmethod
    def _in_range(moment: Optional[datetime], query: TimelineQuery) -> bool:
        if moment is None:
            return False
        return ((query.date_from is None or moment >= query.date_from)
                and (query.date_to is None or moment <= query.date_to))

    async def _rows(self, model, patient_id: uuid.UUID):
        return (await self.session.scalars(select(model).where(model.patient_id == patient_id))).all()

    # ---------------------------------------------------------------- fontes

    async def _registration(self, patient_id):
        patient = await self.session.get(PatientModel, patient_id)
        if not patient or not patient.created_at:
            return []
        return [TimelineEvent(patient.created_at, T.REGISTRATION, "Cadastro do paciente", patient.id)]

    async def _appointments(self, patient_id):
        rows = await self.session.execute(
            select(AppointmentModel, ProfessionalModel.full_name)
            .join(ProfessionalModel, ProfessionalModel.id == AppointmentModel.professional_id)
            .where(AppointmentModel.patient_id == patient_id))
        return [TimelineEvent(
            a.start_time, T.APPOINTMENT,
            f"{APPOINTMENT_TYPE_LABELS.get(a.appointment_type, 'Consulta')} com {professional}",
            a.id, description=a.reason, status=a.status,
        ) for a, professional in rows.all()]

    async def _notes(self, patient_id):
        return [TimelineEvent(n.timestamp, T.CLINICAL_NOTE, "Nota de evolução clínica", n.id,
                              description=_preview(n.content), status=n.status)
                for n in await self._rows(ClinicalNoteModel, patient_id)]

    async def _alerts(self, patient_id):
        return [TimelineEvent(a.created_at, T.ALERT, f"Alerta ({a.severity})", a.id,
                              description=a.description, status="ATIVO" if a.is_active else "INATIVO")
                for a in await self._rows(PatientAlertModel, patient_id)]

    async def _triages(self, patient_id):
        return [TimelineEvent(t.created_at, T.TRIAGE, f"Triagem — {TriagePriority[t.priority].label}", t.id,
                              description=t.main_complaint, status=t.priority)
                for t in await self._rows(TriageModel, patient_id)]

    async def _allergies(self, patient_id):
        events = []
        for a in await self._rows(AllergyModel, patient_id):
            events.append(TimelineEvent(a.recorded_at, T.ALLERGY, f"Alergia registrada: {a.substance}", a.id,
                                        description=a.reaction, status=a.severity))
            if a.resolved_at:
                events.append(TimelineEvent(a.resolved_at, T.ALLERGY, f"Alergia resolvida: {a.substance}", a.id,
                                            status=a.status))
        return events

    async def _conditions(self, patient_id):
        events = []
        for c in await self._rows(ConditionModel, patient_id):
            started = datetime.combine(c.onset_date, time.min) if c.onset_date else c.recorded_at
            events.append(TimelineEvent(started, T.CONDITION, f"Início: {c.name}", c.id,
                                        description=c.notes, status=c.status))
            if c.resolved_date:
                events.append(TimelineEvent(datetime.combine(c.resolved_date, time.min), T.CONDITION,
                                            f"Resolvida: {c.name}", c.id, status=c.status))
        return events

    async def _diagnoses(self, patient_id):
        return [TimelineEvent(d.diagnosed_at, T.DIAGNOSIS, f"Diagnóstico: {d.description}", d.id,
                              description=d.code, status=d.certainty)
                for d in await self._rows(DiagnosisModel, patient_id)]

    async def _procedures(self, patient_id):
        return [TimelineEvent(p.performed_at, T.PROCEDURE, f"Procedimento: {p.name}", p.id, description=p.notes)
                for p in await self._rows(ProcedureModel, patient_id)]
