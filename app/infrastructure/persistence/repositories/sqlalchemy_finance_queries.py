from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.finance_queries import (
    FinanceQueries, InvoiceFilter, InvoiceRow, PaymentRow, ServicePrice, UnbilledService,
)
from app.domain.entities.appointment import AppointmentStatus
from app.domain.entities.billing import (
    CENTS, BillingStatus, BillingType, PaymentMethod, ServiceSource, appointment_price_code, exam_price_code,
)
from app.domain.entities.laboratory import ExamStatus
from app.infrastructure.persistence.models.appointment_model import AppointmentModel
from app.infrastructure.persistence.models.billing_model import BillingItemModel, InvoiceModel
from app.infrastructure.persistence.models.clinical_monitoring_model import ExamRequestModel, ExamTypeModel
from app.infrastructure.persistence.models.finance_model import (
    BillingItemSourceModel, InvoicePaymentModel, ServicePriceModel,
)
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.models.professional_model import ProfessionalModel

APPOINTMENT_LABELS = {"PRIMEIRA_CONSULTA": "Primeira consulta", "RETORNO": "Retorno", "URGENCIA": "Consulta de urgência",
                      "TELECONSULTA": "Teleconsulta"}
# Valores gravados que ainda podem virar "ATRASADO" quando o vencimento passa.
DUE_STATUSES = (BillingStatus.PENDING.value, BillingStatus.PARTIALLY_PAID.value)


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENTS)


class SQLAlchemyFinanceQueries(FinanceQueries):
    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------- faturas

    def _rows_query(self):
        gross = (select(BillingItemModel.invoice_id.label("invoice_id"),
                        func.sum(BillingItemModel.quantity * BillingItemModel.unit_price - BillingItemModel.discount)
                        .label("total"))
                 .group_by(BillingItemModel.invoice_id).subquery())
        paid = (select(InvoicePaymentModel.invoice_id.label("invoice_id"), func.sum(InvoicePaymentModel.amount).label("total"))
                .group_by(InvoicePaymentModel.invoice_id).subquery())
        return (select(InvoiceModel, PatientModel.full_name, gross.c.total, paid.c.total)
                .join(PatientModel, PatientModel.id == InvoiceModel.patient_id)
                .outerjoin(gross, gross.c.invoice_id == InvoiceModel.id)
                .outerjoin(paid, paid.c.invoice_id == InvoiceModel.id))

    @staticmethod
    def _to_row(invoice: InvoiceModel, patient_name: str, gross, paid) -> InvoiceRow:
        return InvoiceRow(id=invoice.id, number=invoice.invoice_number, patient_id=invoice.patient_id,
                          patient_name=patient_name, status=BillingStatus(invoice.status), issue_date=invoice.issue_date,
                          due_date=invoice.due_date, gross_total=money(gross), amount_paid=money(paid),
                          insurance_provider=invoice.insurance_provider,
                          coverage_percentage=money(invoice.insurance_coverage_percentage))

    @staticmethod
    def _status_condition(status: BillingStatus, now: datetime):
        overdue = and_(InvoiceModel.status.in_(DUE_STATUSES), InvoiceModel.due_date < now)
        if status == BillingStatus.OVERDUE:
            return or_(overdue, InvoiceModel.status == BillingStatus.OVERDUE.value)
        if status.value in DUE_STATUSES:
            return and_(InvoiceModel.status == status.value,
                        or_(InvoiceModel.due_date.is_(None), InvoiceModel.due_date >= now))
        return InvoiceModel.status == status.value

    async def invoices(self, filters: InvoiceFilter, now: datetime, limit: int, offset: int):
        conditions = []
        if filters.status:
            conditions.append(self._status_condition(filters.status, now))
        if filters.patient_id:
            conditions.append(InvoiceModel.patient_id == filters.patient_id)
        if filters.issued_from:
            conditions.append(InvoiceModel.issue_date >= filters.issued_from)
        if filters.issued_until:
            conditions.append(InvoiceModel.issue_date < filters.issued_until)
        if filters.number:
            conditions.append(InvoiceModel.invoice_number.ilike(f"%{filters.number}%"))
        total = await self.session.scalar(select(func.count()).select_from(InvoiceModel).where(*conditions))
        result = await self.session.execute(self._rows_query().where(*conditions)
                                            .order_by(InvoiceModel.issue_date.desc(), InvoiceModel.invoice_number.desc())
                                            .limit(limit).offset(offset))
        return [self._to_row(*r) for r in result.all()], total

    async def issued_between(self, start: datetime, end: datetime) -> list[InvoiceRow]:
        result = await self.session.execute(self._rows_query().where(
            InvoiceModel.status != BillingStatus.DRAFT.value, InvoiceModel.issue_date >= start, InvoiceModel.issue_date < end))
        return [self._to_row(*r) for r in result.all()]

    async def open_invoices(self) -> list[InvoiceRow]:
        open_values = [s.value for s in (BillingStatus.PENDING, BillingStatus.PARTIALLY_PAID, BillingStatus.OVERDUE)]
        result = await self.session.execute(self._rows_query().where(InvoiceModel.status.in_(open_values)))
        return [self._to_row(*r) for r in result.all()]

    async def payments_between(self, start: datetime, end: datetime) -> list[PaymentRow]:
        result = await self.session.scalars(select(InvoicePaymentModel).where(
            InvoicePaymentModel.paid_at >= start, InvoicePaymentModel.paid_at < end))
        return [PaymentRow(paid_at=p.paid_at, amount=money(p.amount), method=PaymentMethod(p.method)) for p in result]

    # ---------------------------------------------------- serviços a faturar

    def _billed(self, source: ServiceSource):
        """Ids de atendimentos que já estão em uma fatura não cancelada."""
        return (select(BillingItemSourceModel.source_id)
                .join(BillingItemModel, BillingItemModel.id == BillingItemSourceModel.item_id)
                .join(InvoiceModel, InvoiceModel.id == BillingItemModel.invoice_id)
                .where(BillingItemSourceModel.source_type == source.value,
                       InvoiceModel.status != BillingStatus.CANCELLED.value))

    async def unbilled_services(self, patient_id: uuid.UUID) -> list[UnbilledService]:
        appointments = await self.session.execute(
            select(AppointmentModel, ProfessionalModel.full_name)
            .join(ProfessionalModel, ProfessionalModel.id == AppointmentModel.professional_id)
            .where(AppointmentModel.patient_id == patient_id,
                   AppointmentModel.status == AppointmentStatus.COMPLETED.value,
                   AppointmentModel.id.not_in(self._billed(ServiceSource.APPOINTMENT))))
        exams = await self.session.execute(
            select(ExamRequestModel, ExamTypeModel.code, ExamTypeModel.name)
            .join(ExamTypeModel, ExamTypeModel.id == ExamRequestModel.exam_type_id)
            .where(ExamRequestModel.patient_id == patient_id, ExamRequestModel.status == ExamStatus.RELEASED.value,
                   ExamRequestModel.id.not_in(self._billed(ServiceSource.EXAM))))
        services = [UnbilledService(ServiceSource.APPOINTMENT, a.id, a.start_time,
                                    f"{APPOINTMENT_LABELS.get(a.appointment_type, 'Consulta')} — {doctor}",
                                    appointment_price_code(a.appointment_type)) for a, doctor in appointments.all()]
        services += [UnbilledService(ServiceSource.EXAM, e.id, e.released_at or e.requested_at, f"Exame: {name}",
                                     exam_price_code(code)) for e, code, name in exams.all()]
        return sorted(services, key=lambda s: s.performed_at)

    async def prices(self) -> dict[str, ServicePrice]:
        rows = await self.session.scalars(select(ServicePriceModel).where(ServicePriceModel.active.is_(True))
                                          .order_by(ServicePriceModel.code))
        return {p.code: ServicePrice(p.code, p.description, BillingType(p.billing_type), money(p.price)) for p in rows}

    async def patient_name(self, patient_id: uuid.UUID) -> Optional[str]:
        return await self.session.scalar(select(PatientModel.full_name).where(PatientModel.id == patient_id))
