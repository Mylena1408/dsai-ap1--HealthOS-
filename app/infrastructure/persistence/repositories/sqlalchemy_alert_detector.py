"""Consultas de cada regra de alerta (ver app/application/services/alert_rules.py)."""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.engagement_repository import AlertDetector
from app.application.services import alert_rules as params
from app.domain.entities.appointment import ACTIVE_STATUSES, AppointmentStatus
from app.domain.entities.billing import format_brl
from app.domain.entities.laboratory import ExamStatus
from app.domain.entities.medical_record import ConditionStatus
from app.domain.entities.reference_range import ResultFlag
from app.domain.entities.system_alert import AlertCandidate, AlertCategory as Cat, AlertLevel as Lvl
from app.domain.entities.vital_signs import METRIC_LABELS, VitalMetric, VitalSigns
from app.infrastructure.persistence.models.appointment_model import AppointmentModel
from app.infrastructure.persistence.models.clinical_monitoring_model import (
    ExamRequestModel, ExamTypeModel, VitalSignsModel,
)
from app.infrastructure.persistence.models.medical_record_model import ConditionModel
from app.infrastructure.persistence.models.medication_model import InventoryItemModel, MedicationModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.models.pharmacy_model import StockLotModel
from app.infrastructure.persistence.models.professional_model import ProfessionalModel
from app.infrastructure.persistence.repositories.sqlalchemy_finance_queries import SQLAlchemyFinanceQueries

CRITICAL_FLAGS = {ResultFlag.CRITICAL_LOW.value, ResultFlag.CRITICAL_HIGH.value}


class SQLAlchemyAlertDetector(AlertDetector):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def detect(self, rule_code: str, now: datetime) -> list[AlertCandidate]:
        method = getattr(self, f"_{rule_code.lower()}")
        return await method(now)

    # ---------------------------------------------------------------- estoque

    async def _estoque_baixo(self, now):
        rows = await self.session.execute(
            select(InventoryItemModel, MedicationModel.name)
            .join(MedicationModel, MedicationModel.id == InventoryItemModel.medication_id)
            .where(InventoryItemModel.quantity <= InventoryItemModel.min_threshold))
        return [AlertCandidate(
            rule_code="ESTOQUE_BAIXO", dedup_key=f"ESTOQUE_BAIXO:{item.medication_id}:{item.location_id}",
            category=Cat.STOCK, level=Lvl.CRITICAL if item.quantity <= 0 else Lvl.WARNING,
            title=f"{'Estoque zerado' if item.quantity <= 0 else 'Estoque baixo'}: {name}",
            message=f"{name} em {item.location_id}: {item.quantity:g} unidade(s) (mínimo {item.min_threshold:g}).",
            subject_type="Medicamento", subject_id=item.medication_id, link="/app/farmacia",
        ) for item, name in rows.all()]

    async def _lote_vencendo(self, now):
        limit = now.date() + timedelta(days=params.LOT_EXPIRY_WARNING_DAYS)
        rows = await self.session.execute(
            select(StockLotModel, MedicationModel.name)
            .join(MedicationModel, MedicationModel.id == StockLotModel.medication_id)
            .where(StockLotModel.quantity > 0, StockLotModel.expiration_date <= limit))
        candidates = []
        for lot, name in rows.all():
            expired = lot.expiration_date < now.date()
            days = (lot.expiration_date - now.date()).days
            candidates.append(AlertCandidate(
                rule_code="LOTE_VENCENDO", dedup_key=f"LOTE_VENCENDO:{lot.id}", category=Cat.MEDICATION,
                level=Lvl.CRITICAL if expired else Lvl.WARNING,
                title=f"{'Lote vencido' if expired else 'Lote vencendo'}: {name} ({lot.lot_number})",
                message=(f"Lote {lot.lot_number} em {lot.location} com {lot.quantity:g} unidade(s) "
                         + (f"venceu em {lot.expiration_date:%d/%m/%Y}; separar para descarte."
                            if expired else f"vence em {days} dia(s) ({lot.expiration_date:%d/%m/%Y}).")),
                subject_type="Lote", subject_id=lot.id, link="/app/farmacia"))
        return candidates

    # ---------------------------------------------------------------- consultas

    async def _consulta_proxima_nao_confirmada(self, now):
        rows = await self.session.execute(
            select(AppointmentModel, PatientModel.full_name, ProfessionalModel.full_name)
            .join(PatientModel, PatientModel.id == AppointmentModel.patient_id)
            .join(ProfessionalModel, ProfessionalModel.id == AppointmentModel.professional_id)
            .where(AppointmentModel.status == AppointmentStatus.SCHEDULED.value,
                   AppointmentModel.start_time > now,
                   AppointmentModel.start_time <= now + timedelta(hours=params.UPCOMING_APPOINTMENT_HOURS)))
        return [AlertCandidate(
            rule_code="CONSULTA_PROXIMA_NAO_CONFIRMADA", dedup_key=f"CONSULTA_PROXIMA:{a.id}",
            category=Cat.APPOINTMENT, level=Lvl.INFO, title=f"Confirmar consulta de {patient}",
            message=f"Consulta com {professional} em {a.start_time:%d/%m/%Y %H:%M} ainda não confirmada.",
            subject_type="Consulta", subject_id=a.id, patient_id=a.patient_id, link="/app/consultas",
        ) for a, patient, professional in rows.all()]

    # ---------------------------------------------------------------- laboratório

    async def _exame_fora_referencia(self, now):
        rows = await self.session.execute(
            select(ExamRequestModel, ExamTypeModel.name, PatientModel.full_name)
            .join(ExamTypeModel, ExamTypeModel.id == ExamRequestModel.exam_type_id)
            .join(PatientModel, PatientModel.id == ExamRequestModel.patient_id)
            .where(ExamRequestModel.status == ExamStatus.RELEASED.value,
                   ExamRequestModel.released_at >= now - timedelta(days=params.ABNORMAL_EXAM_WINDOW_DAYS)))
        candidates = []
        for exam, exam_name, patient in rows.all():
            abnormal = [r for r in exam.results if r.flag != ResultFlag.NORMAL.value]
            if not abnormal:
                continue
            critical = any(r.flag in CRITICAL_FLAGS for r in abnormal)
            candidates.append(AlertCandidate(
                rule_code="EXAME_FORA_REFERENCIA", dedup_key=f"EXAME_FORA_REFERENCIA:{exam.id}",
                category=Cat.LABORATORY, level=Lvl.CRITICAL if critical else Lvl.WARNING,
                title=f"{exam_name} fora da referência — {patient}",
                message="; ".join(f"{r.analyte_name}: {r.value:g} {r.unit} (ref. {r.reference_text})" for r in abnormal),
                subject_type="Exame", subject_id=exam.id, patient_id=exam.patient_id,
                link=f"/app/prontuario?patient={exam.patient_id}"))
        return candidates

    async def _exame_atrasado(self, now):
        rows = await self.session.execute(
            select(ExamRequestModel, ExamTypeModel.name, ExamTypeModel.turnaround_hours, PatientModel.full_name)
            .join(ExamTypeModel, ExamTypeModel.id == ExamRequestModel.exam_type_id)
            .join(PatientModel, PatientModel.id == ExamRequestModel.patient_id)
            .where(ExamRequestModel.status.in_([ExamStatus.COLLECTED.value, ExamStatus.PROCESSING.value]),
                   ExamRequestModel.collected_at.is_not(None)))
        candidates = []
        for exam, name, turnaround, patient in rows.all():
            due = exam.collected_at + timedelta(hours=turnaround)
            if due >= now:
                continue
            candidates.append(AlertCandidate(
                rule_code="EXAME_ATRASADO", dedup_key=f"EXAME_ATRASADO:{exam.id}", category=Cat.LABORATORY,
                level=Lvl.WARNING, title=f"{name} atrasado — {patient}",
                message=f"Amostra {exam.sample_code} coletada em {exam.collected_at:%d/%m %H:%M}; "
                        f"prazo era {due:%d/%m %H:%M}.",
                subject_type="Exame", subject_id=exam.id, patient_id=exam.patient_id, link="/app/laboratorio"))
        return candidates

    # ---------------------------------------------------------------- clínico

    async def _sinal_vital_critico(self, now):
        window_start = now - timedelta(days=params.CRITICAL_VITALS_WINDOW_DAYS)
        latest = (select(VitalSignsModel.patient_id, func.max(VitalSignsModel.recorded_at).label("last"))
                  .where(VitalSignsModel.recorded_at >= window_start).group_by(VitalSignsModel.patient_id).subquery())
        rows = await self.session.execute(
            select(VitalSignsModel, PatientModel.full_name)
            .join(latest, (latest.c.patient_id == VitalSignsModel.patient_id) & (latest.c.last == VitalSignsModel.recorded_at))
            .join(PatientModel, PatientModel.id == VitalSignsModel.patient_id))
        candidates = []
        for v, patient in rows.all():
            # Considera só a medição mais recente: uma nova medição normal resolve o alerta.
            vitals = VitalSigns(patient_id=v.patient_id, recorded_at=v.recorded_at,
                                **{m.value: getattr(v, m.value) for m in VitalMetric if m != VitalMetric.BMI})
            critical = [METRIC_LABELS[m] for m, flag in vitals.flags().items() if flag.is_critical]
            if critical:
                candidates.append(AlertCandidate(
                    rule_code="SINAL_VITAL_CRITICO", dedup_key=f"SINAL_VITAL_CRITICO:{v.patient_id}",
                    category=Cat.CLINICAL, level=Lvl.CRITICAL, title=f"Sinal vital crítico — {patient}",
                    message=f"Medição de {v.recorded_at:%d/%m %H:%M} com valor crítico em: {', '.join(critical)}.",
                    subject_type="Paciente", subject_id=v.patient_id, patient_id=v.patient_id,
                    link=f"/app/prontuario?patient={v.patient_id}"))
        return candidates

    async def _paciente_sem_acompanhamento(self, now):
        with_condition = select(ConditionModel.patient_id).where(
            ConditionModel.status == ConditionStatus.ACTIVE.value).distinct()
        last_visit = dict((await self.session.execute(
            select(AppointmentModel.patient_id, func.max(AppointmentModel.start_time))
            .where(AppointmentModel.status == AppointmentStatus.COMPLETED.value)
            .group_by(AppointmentModel.patient_id))).all())
        upcoming = set((await self.session.scalars(
            select(AppointmentModel.patient_id).where(
                AppointmentModel.status.in_([s.value for s in ACTIVE_STATUSES]),
                AppointmentModel.start_time > now))).all())
        patients = (await self.session.execute(
            select(PatientModel.id, PatientModel.full_name).where(PatientModel.id.in_(with_condition)))).all()
        limit = now - timedelta(days=params.FOLLOW_UP_GAP_DAYS)
        candidates = []
        for patient_id, name in patients:
            last = last_visit.get(patient_id)
            if patient_id in upcoming or (last and last >= limit):
                continue
            candidates.append(AlertCandidate(
                rule_code="PACIENTE_SEM_ACOMPANHAMENTO", dedup_key=f"SEM_ACOMPANHAMENTO:{patient_id}",
                category=Cat.CLINICAL, level=Lvl.INFO, title=f"Sem acompanhamento recente — {name}",
                message=("Possui condição ativa e " + (f"a última consulta finalizada foi em {last:%d/%m/%Y}"
                         if last else "nenhuma consulta finalizada registrada") + "; não há consulta futura agendada."),
                subject_type="Paciente", subject_id=patient_id, patient_id=patient_id,
                link=f"/app/prontuario?patient={patient_id}"))
        return candidates

    # -------------------------------------------------------------- financeiro

    async def _fatura_vencida(self, now):
        candidates = []
        for invoice in await SQLAlchemyFinanceQueries(self.session).open_invoices():
            if invoice.due_date is None or invoice.due_date >= now:
                continue
            days = (now - invoice.due_date).days
            balance = invoice.gross_total - invoice.amount_paid
            candidates.append(AlertCandidate(
                rule_code="FATURA_VENCIDA", dedup_key=f"FATURA_VENCIDA:{invoice.id}", category=Cat.ADMINISTRATIVE,
                level=Lvl.CRITICAL if days > params.INVOICE_OVERDUE_CRITICAL_DAYS else Lvl.WARNING,
                title=f"Fatura vencida: {invoice.number} — {invoice.patient_name}",
                message=f"Saldo de {format_brl(balance)} vencido em {invoice.due_date:%d/%m/%Y} ({days} dia(s)).",
                subject_type="Fatura", subject_id=invoice.id, patient_id=invoice.patient_id, link="/app/financeiro"))
        return candidates

