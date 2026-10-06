"""Painéis por perfil: paciente, profissional, farmácia e administração.

Compõe os casos de uso existentes (sem duplicar regras) e usa o repositório de
indicadores apenas para agregações.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable
import uuid

from app.application.dtos.dashboard_dto import (
    AdminDashboardDTO, DailyPoint, HealthScoreDTO, PatientDashboardDTO, PharmacyDashboardDTO,
    ProfessionalDashboardDTO, RankedItem, ScoreComponentDTO,
)
from app.application.dtos.engagement_dto import SystemAlertDTO
from app.application.interfaces.analytics_repository import AnalyticsRepository
from app.application.interfaces.appointment_repository import AppointmentFilters
from app.application.interfaces.clinical_monitoring_repository import ExamRequestFilters
from app.application.interfaces.engagement_repository import (
    AlertFilters, InboxQuery, InboxRepository, SystemAlertRepository,
)
from app.application.interfaces.medical_record_repository import PatientDirectoryRepository
from app.application.interfaces.pharmacy_repository import LotFilters, PrescriptionFilters
from app.application.interfaces.professional_repository import ProfessionalRepository
from app.application.use_cases.appointment_use_case import AppointmentUseCase
from app.application.use_cases.laboratory_use_case import LaboratoryUseCase
from app.application.use_cases.medical_record_use_case import age_on
from app.application.use_cases.pharmacy_stock_use_case import PharmacyStockUseCase
from app.application.use_cases.prescription_use_case import PrescriptionUseCase
from app.application.use_cases.vital_signs_use_case import VitalSignsUseCase
from app.domain.entities.appointment import ACTIVE_STATUSES, AppointmentStatus
from app.domain.entities.inbox import Audience, InboxStatus
from app.domain.entities.laboratory import ExamStatus
from app.domain.entities.pharmacy import ItemStatus, PrescriptionStatus
from app.domain.entities.system_alert import AlertCategory, SystemAlert, SystemAlertStatus
from app.domain.exceptions.common import EntityNotFoundError
from app.domain.services.health_score import compute_health_score

OPEN = [SystemAlertStatus.ACTIVE, SystemAlertStatus.ACKNOWLEDGED]
WINDOW_DAYS = 30


def _alert_dto(alert: SystemAlert) -> SystemAlertDTO:
    return SystemAlertDTO(**{name: getattr(alert, name) for name in SystemAlertDTO.model_fields})


def last_months(today: date, count: int) -> list[date]:
    """Primeiro dia de cada um dos últimos `count` meses, do mais antigo ao atual."""
    months, year, month = [], today.year, today.month
    for _ in range(count):
        months.append(date(year, month, 1))
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    return months[::-1]


def daily_series(rows: list[tuple[datetime, str]], start: date, days: int, keys: list[str]) -> list[DailyPoint]:
    """Conta ocorrências por dia e por chave, preenchendo dias vazios com zero."""
    buckets: dict[date, Counter] = defaultdict(Counter)
    for moment, key in rows:
        buckets[moment.date()][key] += 1
    return [DailyPoint(day=start + timedelta(days=i),
                       values={k: float(buckets[start + timedelta(days=i)][k]) for k in keys}) for i in range(days)]


@dataclass
class DashboardDeps:
    analytics: AnalyticsRepository
    directory: PatientDirectoryRepository
    professional_repo: ProfessionalRepository
    alerts: SystemAlertRepository
    inbox: InboxRepository
    appointments: AppointmentUseCase
    laboratory: LaboratoryUseCase
    vitals: VitalSignsUseCase
    prescriptions: PrescriptionUseCase
    stock: PharmacyStockUseCase


class DashboardUseCase:

    def __init__(self, deps: DashboardDeps, clock: Callable[[], datetime] = datetime.now):
        self.d = deps
        self.clock = clock

    # ------------------------------------------------------------ Health Score

    async def health_score(self, patient_id: uuid.UUID) -> HealthScoreDTO:
        if not await self.d.directory.get(patient_id):
            raise EntityNotFoundError("Paciente", patient_id)
        now = self.clock()
        inputs = (await self.d.analytics.health_inputs(now, {patient_id}))[patient_id]
        return self._score_dto(patient_id, inputs, now)

    def _score_dto(self, patient_id, inputs, now) -> HealthScoreDTO:
        result = compute_health_score(inputs, now.date())
        return HealthScoreDTO(
            patient_id=patient_id, score=result.score, band=result.band, computed_at=now, disclaimer=result.disclaimer,
            components=[ScoreComponentDTO(key=c.key, label=c.label, score=c.score, applicable=c.applicable,
                                          explanation=c.explanation) for c in result.components])

    # ------------------------------------------------------------------ painéis

    async def patient(self, patient_id: uuid.UUID) -> PatientDashboardDTO:
        patient = await self.d.directory.get(patient_id)
        if not patient:
            raise EntityNotFoundError("Paciente", patient_id)
        now = self.clock()
        upcoming = await self.d.appointments.search(AppointmentFilters(
            patient_id=patient_id, statuses=list(ACTIVE_STATUSES), date_from=now, limit=5))
        exams = await self.d.laboratory.search(ExamRequestFilters(
            patient_id=patient_id, statuses=[ExamStatus.RELEASED], limit=5))
        alerts, _ = await self.d.alerts.search(AlertFilters(statuses=OPEN, patient_id=patient_id, limit=10))
        unread = await self.d.inbox.counts(InboxQuery(audience=Audience.PATIENT, recipient_id=patient_id))
        return PatientDashboardDTO(
            patient_id=patient_id, patient_name=patient.full_name, age=age_on(patient.birth_date, now.date()),
            health_score=await self.health_score(patient_id), upcoming_appointments=upcoming.items,
            medications_in_use=await self.d.prescriptions.patient_medications(patient_id, ItemStatus.IN_USE),
            recent_exams=exams.items, vitals=(await self.d.vitals.summary(patient_id)).metrics,
            open_alerts=[_alert_dto(a) for a in alerts], unread_notifications=unread.get(InboxStatus.UNREAD, 0))

    async def professional(self, professional_id: uuid.UUID) -> ProfessionalDashboardDTO:
        professional = await self.d.professional_repo.get_by_id(professional_id)
        if not professional:
            raise EntityNotFoundError("Profissional", professional_id)
        now = self.clock()
        today = datetime.combine(now.date(), datetime.min.time())
        start = today - timedelta(days=WINDOW_DAYS - 1)
        agenda = await self.d.appointments.search(AppointmentFilters(
            professional_id=professional_id, date_from=today, date_to=today + timedelta(days=1), limit=50))
        upcoming = await self.d.appointments.search(AppointmentFilters(
            professional_id=professional_id, statuses=list(ACTIVE_STATUSES), date_from=now,
            date_to=today + timedelta(days=8), limit=1))
        rows = await self.d.analytics.appointment_rows(start, today + timedelta(days=1), professional_id)
        counts = Counter(status for _, status in rows)
        attended = counts[AppointmentStatus.COMPLETED.value] + counts[AppointmentStatus.NO_SHOW.value]
        abnormal = await self.d.laboratory.search(ExamRequestFilters(
            statuses=[ExamStatus.RELEASED], only_abnormal=True, requested_by=professional_id,
            date_from=now - timedelta(days=WINDOW_DAYS), limit=10))
        unread = await self.d.inbox.counts(InboxQuery(audience=Audience.PROFESSIONAL, recipient_id=professional_id))
        keys = [AppointmentStatus.COMPLETED.value, AppointmentStatus.CANCELLED.value, AppointmentStatus.NO_SHOW.value]
        return ProfessionalDashboardDTO(
            professional_id=professional_id, professional_name=professional.full_name, today=agenda.items,
            next_7_days=upcoming.total, appointments_30d=dict(counts),
            patients_seen_30d=await self.d.analytics.distinct_patients_seen(professional_id, start),
            attendance_rate_30d=round(counts[AppointmentStatus.COMPLETED.value] / attended, 3) if attended else None,
            exams_requested=await self.d.analytics.exam_status_counts(requested_by=professional_id),
            recent_abnormal_exams=abnormal.items,
            daily_30d=daily_series(rows, start.date(), WINDOW_DAYS, keys),
            unread_notifications=unread.get(InboxStatus.UNREAD, 0))

    async def pharmacy(self) -> PharmacyDashboardDTO:
        now = self.clock()
        start = datetime.combine(now.date(), datetime.min.time()) - timedelta(days=WINDOW_DAYS - 1)
        overview = await self.d.stock.overview()
        expiring = await self.d.stock.search_lots(LotFilters(expiring_before=now.date() + timedelta(days=30), limit=1000))
        queue = await self.d.prescriptions.search(PrescriptionFilters(
            statuses=[PrescriptionStatus.ACTIVE, PrescriptionStatus.PARTIALLY_DISPENSED], limit=100))
        rows = await self.d.analytics.dispensation_rows(start)
        units_by_day: dict[date, float] = defaultdict(float)
        units_by_medication: Counter = Counter()
        for moment, medication, quantity in rows:
            units_by_day[moment.date()] += quantity
            units_by_medication[medication] += quantity
        alerts, _ = await self.d.alerts.search(AlertFilters(
            statuses=OPEN, categories=[AlertCategory.STOCK, AlertCategory.MEDICATION], limit=10))
        return PharmacyDashboardDTO(
            items_below_minimum=sum(1 for o in overview if o.below_minimum_locations),
            zero_stock=sum(1 for o in overview if o.total_quantity <= 0),
            lots_expiring_30d=sum(1 for lot in expiring.items if not lot.is_expired),
            lots_expired=sum(1 for lot in expiring.items if lot.is_expired),
            dispensation_queue=sum(1 for p in queue.items if not p.is_expired),
            units_dispensed_30d=sum(units_by_day.values()),
            daily_30d=[DailyPoint(day=start.date() + timedelta(days=i),
                                  values={"unidades": units_by_day[start.date() + timedelta(days=i)]})
                       for i in range(WINDOW_DAYS)],
            top_medications_30d=[RankedItem(label=name, value=units) for name, units in units_by_medication.most_common(5)],
            open_alerts=[_alert_dto(a) for a in alerts])

    async def admin(self) -> AdminDashboardDTO:
        now = self.clock()
        today = datetime.combine(now.date(), datetime.min.time())
        start = today - timedelta(days=WINDOW_DAYS - 1)
        rows = await self.d.analytics.appointment_rows(start, today + timedelta(days=1))
        keys = [AppointmentStatus.COMPLETED.value, AppointmentStatus.CANCELLED.value, AppointmentStatus.NO_SHOW.value]

        months = last_months(today.date(), 6)
        registrations = Counter(moment.strftime("%Y-%m") for moment in
                                await self.d.analytics.patient_registrations(
                                    datetime.combine(months[0], datetime.min.time())) if moment)

        # Entradas de todos os pacientes calculadas em lote (sem uma consulta por paciente).
        results = [compute_health_score(inputs, now.date())
                   for inputs in (await self.d.analytics.health_inputs(now)).values()]
        valid = [r.score for r in results if r.score is not None]
        distribution = Counter(r.band.value if r.band else "SEM_DADOS" for r in results)

        return AdminDashboardDTO(
            counts=await self.d.analytics.entity_counts(), appointments_30d=dict(Counter(s for _, s in rows)),
            daily_appointments_30d=daily_series(rows, start.date(), WINDOW_DAYS, keys),
            exams_90d=await self.d.analytics.exam_status_counts(since=now - timedelta(days=90)),
            prescriptions_30d=await self.d.analytics.prescriptions_since(now - timedelta(days=WINDOW_DAYS)),
            alerts_open=await self.d.alerts.summary(),
            new_patients_monthly=[RankedItem(label=m.strftime("%m/%Y"), value=registrations[m.strftime("%Y-%m")])
                                  for m in months],
            health_score_distribution={key: distribution.get(key, 0)
                                       for key in ("BOM", "ATENCAO", "INSUFICIENTE", "SEM_DADOS")},
            health_score_average=round(sum(valid) / len(valid), 1) if valid else None)
