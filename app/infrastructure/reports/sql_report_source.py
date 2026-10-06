"""Consultas de cada relatório do catálogo (app/application/services/report_catalog.py)."""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.finance_queries import InvoiceFilter
from app.application.interfaces.report_source import ReportQuery, ReportSource
from app.application.services.alert_rules import LOT_EXPIRY_WARNING_DAYS
from app.application.use_cases.finance_use_case import PRIVATE_PAYER, effective_status
from app.domain.entities.billing import BillingStatus
from app.infrastructure.persistence.models.appointment_model import AppointmentModel
from app.infrastructure.persistence.models.clinical_monitoring_model import ExamRequestModel, ExamTypeModel
from app.infrastructure.persistence.models.engagement_model import AuditEventModel
from app.infrastructure.persistence.models.medication_model import MedicationModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.models.pharmacy_model import (
    DispensationLineModel, DispensationModel, StockLotModel,
)
from app.infrastructure.persistence.models.professional_model import ProfessionalModel
from app.infrastructure.persistence.repositories.sqlalchemy_finance_queries import SQLAlchemyFinanceQueries


def in_period(column, query: ReportQuery):
    return [column >= query.start, column < query.end]


class SQLAlchemyReportSource(ReportSource):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def rows(self, report_key: str, query: ReportQuery):
        return await getattr(self, f"_{report_key}")(query)

    async def _consultas(self, q: ReportQuery):
        stmt = (select(AppointmentModel, PatientModel.full_name, ProfessionalModel.full_name)
                .join(PatientModel, PatientModel.id == AppointmentModel.patient_id)
                .join(ProfessionalModel, ProfessionalModel.id == AppointmentModel.professional_id)
                .where(*in_period(AppointmentModel.start_time, q)))
        if q.status:
            stmt = stmt.where(AppointmentModel.status == q.status)
        result = await self.session.execute(stmt.order_by(AppointmentModel.start_time).limit(q.limit))
        return [dict(start_time=a.start_time, patient=patient, professional=professional, type=a.appointment_type,
                     status=a.status) for a, patient, professional in result.all()]

    async def _exames(self, q: ReportQuery):
        stmt = (select(ExamRequestModel, PatientModel.full_name, ExamTypeModel.name)
                .join(PatientModel, PatientModel.id == ExamRequestModel.patient_id)
                .join(ExamTypeModel, ExamTypeModel.id == ExamRequestModel.exam_type_id)
                .where(*in_period(ExamRequestModel.requested_at, q)))
        if q.status:
            stmt = stmt.where(ExamRequestModel.status == q.status)
        result = await self.session.execute(stmt.order_by(ExamRequestModel.requested_at).limit(q.limit))
        return [dict(requested_at=e.requested_at, patient=patient, exam=exam, priority=e.priority, status=e.status,
                     released_at=e.released_at) for e, patient, exam in result.all()]

    async def _dispensacoes(self, q: ReportQuery):
        result = await self.session.execute(
            select(DispensationModel, DispensationLineModel, PatientModel.full_name, MedicationModel.name)
            .join(DispensationLineModel, DispensationLineModel.dispensation_id == DispensationModel.id)
            .join(PatientModel, PatientModel.id == DispensationModel.patient_id)
            .join(MedicationModel, MedicationModel.id == DispensationLineModel.medication_id)
            .where(*in_period(DispensationModel.dispensed_at, q))
            .order_by(DispensationModel.dispensed_at, MedicationModel.name).limit(q.limit))
        return [dict(dispensed_at=d.dispensed_at, patient=patient, medication=medication, lot=line.lot_number or "—",
                     quantity=line.quantity, location=d.location) for d, line, patient, medication in result.all()]

    async def _estoque(self, q: ReportQuery):
        today = q.now.date()
        warning = today + timedelta(days=LOT_EXPIRY_WARNING_DAYS)
        result = await self.session.execute(
            select(StockLotModel, MedicationModel.name)
            .join(MedicationModel, MedicationModel.id == StockLotModel.medication_id)
            .where(StockLotModel.quantity > 0)
            .order_by(MedicationModel.name, StockLotModel.expiration_date).limit(q.limit))

        def situation(expiration):
            if expiration < today:
                return "VENCIDO"
            return "VENCENDO" if expiration <= warning else "OK"

        return [dict(medication=name, lot=lot.lot_number, location=lot.location, expiration_date=lot.expiration_date,
                     quantity=lot.quantity, situation=situation(lot.expiration_date)) for lot, name in result.all()]

    async def _faturas(self, q: ReportQuery):
        filters = InvoiceFilter(status=BillingStatus(q.status) if q.status else None,
                                issued_from=q.start, issued_until=q.end)
        rows, _ = await SQLAlchemyFinanceQueries(self.session).invoices(filters, q.now, q.limit, 0)
        rows.reverse()  # a consulta do financeiro traz as mais recentes primeiro; o relatório é cronológico
        return [dict(number=r.number, patient=r.patient_name, issue_date=r.issue_date.date() if r.issue_date else None,
                     due_date=r.due_date.date() if r.due_date else None,
                     payer=r.insurance_provider if r.coverage_percentage else PRIVATE_PAYER,
                     gross_total=r.gross_total, amount_paid=r.amount_paid, balance=r.gross_total - r.amount_paid,
                     status=effective_status(r, q.now).value) for r in rows]

    async def _auditoria(self, q: ReportQuery):
        result = await self.session.scalars(
            select(AuditEventModel).where(*in_period(AuditEventModel.occurred_at, q))
            .order_by(AuditEventModel.occurred_at).limit(q.limit))
        return [dict(occurred_at=e.occurred_at, event_type=e.event_type, entity_type=e.entity_type, summary=e.summary)
                for e in result]
