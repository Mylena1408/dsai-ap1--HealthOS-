"""Agregações para painéis. Agrupamentos por dia/mês são feitos em Python sobre colunas
leves, para funcionar igual em SQLite e PostgreSQL (que têm funções de data diferentes)."""
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.analytics_repository import AnalyticsRepository
from app.domain.entities.appointment import ACTIVE_STATUSES, AppointmentStatus
from app.domain.entities.laboratory import ExamStatus
from app.domain.entities.medical_record import ConditionStatus
from app.domain.entities.pharmacy import ItemStatus, PrescriptionStatus
from app.domain.entities.professional import ProfessionalStatus
from app.domain.entities.reference_range import ResultFlag
from app.domain.entities.vital_signs import VitalMetric, VitalSigns
from app.domain.services.health_score import HealthScoreInputs
from app.infrastructure.persistence.models.appointment_model import AppointmentModel
from app.infrastructure.persistence.models.clinical_monitoring_model import (
    ExamRequestModel, ExamResultModel, ExamTypeModel, VitalSignsModel,
)
from app.infrastructure.persistence.models.medical_record_model import ConditionModel
from app.infrastructure.persistence.models.medication_model import MedicationModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.models.pharmacy_model import (
    DispensationLineModel, DispensationModel, PrescriptionItemModel, PrescriptionModel,
)
from app.infrastructure.persistence.models.professional_model import ProfessionalModel

CRITICAL = (ResultFlag.CRITICAL_LOW.value, ResultFlag.CRITICAL_HIGH.value)


class SQLAlchemyAnalyticsRepository(AnalyticsRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    def _scope(self, column, patient_ids):
        return [column.in_(patient_ids)] if patient_ids is not None else []

    async def health_inputs(self, now, patient_ids=None):
        year_ago, quarter_ago = now - timedelta(days=365), now - timedelta(days=90)
        ids = patient_ids if patient_ids is not None else set(
            (await self.session.scalars(select(PatientModel.id))).all())
        inputs = {pid: HealthScoreInputs() for pid in ids}
        if not ids:
            return inputs

        # Consultas: comparecimentos, faltas, última finalizada e futuras.
        rows = await self.session.execute(
            select(AppointmentModel.patient_id, AppointmentModel.status, func.count(), func.max(AppointmentModel.start_time))
            .where(AppointmentModel.patient_id.in_(ids), AppointmentModel.start_time >= year_ago,
                   AppointmentModel.start_time <= now)
            .group_by(AppointmentModel.patient_id, AppointmentModel.status))
        for pid, status, total, last in rows.all():
            if status == AppointmentStatus.COMPLETED.value:
                inputs[pid].completed_appointments, inputs[pid].last_completed_appointment = total, last
            elif status == AppointmentStatus.NO_SHOW.value:
                inputs[pid].no_show_appointments = total
        for pid in (await self.session.scalars(select(AppointmentModel.patient_id).where(
                AppointmentModel.patient_id.in_(ids), AppointmentModel.start_time > now,
                AppointmentModel.status.in_([s.value for s in ACTIVE_STATUSES])).distinct())).all():
            inputs[pid].has_upcoming_appointment = True

        # Exames: solicitados (não cancelados), liberados, atrasados e valores críticos.
        rows = await self.session.execute(
            select(ExamRequestModel.patient_id, ExamRequestModel.status, ExamRequestModel.collected_at,
                   ExamTypeModel.turnaround_hours)
            .join(ExamTypeModel, ExamTypeModel.id == ExamRequestModel.exam_type_id)
            .where(ExamRequestModel.patient_id.in_(ids), ExamRequestModel.requested_at >= year_ago,
                   ExamRequestModel.status != ExamStatus.CANCELLED.value))
        for pid, status, collected_at, turnaround in rows.all():
            inputs[pid].exams_requested += 1
            if status == ExamStatus.RELEASED.value:
                inputs[pid].exams_released += 1
            elif (status in (ExamStatus.COLLECTED.value, ExamStatus.PROCESSING.value) and collected_at
                  and collected_at + timedelta(hours=turnaround) < now):
                inputs[pid].exams_overdue += 1
        rows = await self.session.execute(
            select(ExamRequestModel.patient_id, func.count())
            .join(ExamResultModel, ExamResultModel.exam_request_id == ExamRequestModel.id)
            .where(ExamRequestModel.patient_id.in_(ids), ExamRequestModel.status == ExamStatus.RELEASED.value,
                   ExamRequestModel.released_at >= year_ago, ExamResultModel.flag.in_(CRITICAL))
            .group_by(ExamRequestModel.patient_id))
        for pid, total in rows.all():
            inputs[pid].critical_exam_results = total

        # Medicamentos: quantidade prescrita x dispensada (90 dias, itens em uso ou concluídos).
        rows = await self.session.execute(
            select(PrescriptionModel.patient_id, func.sum(PrescriptionItemModel.quantity),
                   func.sum(PrescriptionItemModel.dispensed_quantity))
            .join(PrescriptionItemModel, PrescriptionItemModel.prescription_id == PrescriptionModel.id)
            .where(PrescriptionModel.patient_id.in_(ids), PrescriptionModel.issued_at >= quarter_ago,
                   PrescriptionModel.status != PrescriptionStatus.CANCELLED.value,
                   PrescriptionItemModel.status != ItemStatus.SUSPENDED.value)
            .group_by(PrescriptionModel.patient_id))
        for pid, prescribed, dispensed in rows.all():
            inputs[pid].prescribed_quantity, inputs[pid].dispensed_quantity = prescribed or 0, dispensed or 0

        # Monitoramento: quantidade de medições em 90 dias e a fração alterada da mais recente.
        rows = await self.session.execute(
            select(VitalSignsModel).where(VitalSignsModel.patient_id.in_(ids), VitalSignsModel.recorded_at >= quarter_ago)
            .order_by(VitalSignsModel.patient_id, VitalSignsModel.recorded_at))
        latest = {}
        for model in rows.scalars():
            inputs[model.patient_id].vitals_recent += 1
            latest[model.patient_id] = model
        for pid, model in latest.items():
            flags = VitalSigns(patient_id=pid, recorded_at=model.recorded_at, **{
                m.value: getattr(model, m.value) for m in VitalMetric if m != VitalMetric.BMI}).flags()
            if flags:
                inputs[pid].latest_vitals_abnormal_ratio = sum(f.is_abnormal for f in flags.values()) / len(flags)

        rows = await self.session.execute(
            select(ConditionModel.patient_id, func.count())
            .where(ConditionModel.patient_id.in_(ids), ConditionModel.status == ConditionStatus.ACTIVE.value)
            .group_by(ConditionModel.patient_id))
        for pid, total in rows.all():
            inputs[pid].active_conditions = total
        return inputs

    async def appointment_rows(self, date_from, date_to, professional_id=None):
        conditions = [AppointmentModel.start_time >= date_from, AppointmentModel.start_time < date_to]
        if professional_id:
            conditions.append(AppointmentModel.professional_id == professional_id)
        rows = await self.session.execute(select(AppointmentModel.start_time, AppointmentModel.status).where(*conditions))
        return [tuple(r) for r in rows.all()]

    async def distinct_patients_seen(self, professional_id, since):
        return await self.session.scalar(
            select(func.count(func.distinct(AppointmentModel.patient_id))).where(
                AppointmentModel.professional_id == professional_id, AppointmentModel.start_time >= since,
                AppointmentModel.status == AppointmentStatus.COMPLETED.value))

    async def exam_status_counts(self, since=None, requested_by=None):
        conditions = []
        if since:
            conditions.append(ExamRequestModel.requested_at >= since)
        if requested_by:
            conditions.append(ExamRequestModel.requested_by == requested_by)
        rows = await self.session.execute(select(ExamRequestModel.status, func.count())
                                          .where(*conditions).group_by(ExamRequestModel.status))
        return dict(rows.all())

    async def released_exam_dates(self, since):
        return list((await self.session.scalars(select(ExamRequestModel.released_at).where(
            ExamRequestModel.status == ExamStatus.RELEASED.value, ExamRequestModel.released_at >= since))).all())

    async def dispensation_rows(self, since):
        rows = await self.session.execute(
            select(DispensationModel.dispensed_at, MedicationModel.name, DispensationLineModel.quantity)
            .join(DispensationLineModel, DispensationLineModel.dispensation_id == DispensationModel.id)
            .join(MedicationModel, MedicationModel.id == DispensationLineModel.medication_id)
            .where(DispensationModel.dispensed_at >= since))
        return [tuple(r) for r in rows.all()]

    async def entity_counts(self):
        async def count(model, *conditions):
            return await self.session.scalar(select(func.count()).select_from(model).where(*conditions))
        return {
            "patients": await count(PatientModel),
            "professionals_active": await count(ProfessionalModel, ProfessionalModel.status == ProfessionalStatus.ACTIVE.value),
            "medications": await count(MedicationModel),
            "exam_types": await count(ExamTypeModel),
        }

    async def patient_registrations(self, since):
        return list((await self.session.scalars(
            select(PatientModel.created_at).where(PatientModel.created_at >= since))).all())

    async def prescriptions_since(self, since):
        rows = await self.session.execute(select(PrescriptionModel.status, func.count())
                                          .where(PrescriptionModel.issued_at >= since).group_by(PrescriptionModel.status))
        return dict(rows.all())
