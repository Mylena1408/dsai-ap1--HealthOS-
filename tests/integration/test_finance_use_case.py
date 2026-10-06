from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.application.dtos.finance_dto import InvoiceFromServicesDTO, ServiceRefDTO
from app.application.interfaces.finance_queries import InvoiceFilter
from app.application.services.events import InProcessPublisher
from app.application.use_cases.alert_engine_use_case import AlertEngineUseCase
from app.application.use_cases.finance_use_case import FinanceUseCase
from app.domain.entities.billing import BillingStatus, PaymentMethod
from app.domain.events import EventType
from app.domain.exceptions.common import BusinessRuleViolation, ConflictError
from app.infrastructure.persistence.models.billing_model import InvoiceModel
from app.infrastructure.persistence.models.finance_model import InvoicePaymentModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.repositories.sqlalchemy_alert_detector import SQLAlchemyAlertDetector
from app.infrastructure.persistence.repositories.sqlalchemy_billing_repository import SQLAlchemyBillingRepository
from app.infrastructure.persistence.repositories.sqlalchemy_engagement_repository import SQLAlchemySystemAlertRepository
from app.infrastructure.persistence.repositories.sqlalchemy_finance_queries import SQLAlchemyFinanceQueries
from tests.integration.conftest import SEED_NOW


class MovableClock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
async def finance(seeded):
    s = seeded["session"]
    clock = MovableClock(SEED_NOW)
    events = InProcessPublisher()
    return dict(session=s, clock=clock, events=events,
                use_case=FinanceUseCase(SQLAlchemyBillingRepository(s), SQLAlchemyFinanceQueries(s), events, clock))


async def patient_with_unbilled(finance):
    for patient_id in await finance["session"].scalars(select(PatientModel.id).order_by(PatientModel.cpf)):
        services = await finance["use_case"].unbilled(patient_id)
        if len(services) >= 2:
            return patient_id, services
    pytest.skip("seed sem paciente com dois atendimentos a faturar")


def refs(services):
    return [ServiceRefDTO(source_type=s.source_type, source_id=s.source_id) for s in services]


async def test_seed_invoices_are_consistent(finance):
    session, uc = finance["session"], finance["use_case"]
    assert await session.scalar(select(func.count()).select_from(InvoiceModel)) > 0
    page = await uc.page(InvoiceFilter(), 100, 0)
    for item in page.items:
        assert item.amount_paid <= item.gross_total
        assert item.balance == item.gross_total - item.amount_paid
        if item.status == BillingStatus.PAID:
            assert item.balance == 0

    overdue = await uc.page(InvoiceFilter(status=BillingStatus.OVERDUE), 100, 0)
    assert all(i.due_date < SEED_NOW and i.balance > 0 for i in overdue.items)
    pending = await uc.page(InvoiceFilter(status=BillingStatus.PENDING), 100, 0)
    assert all(i.due_date >= SEED_NOW for i in pending.items)  # vencidas não aparecem como pendentes


async def test_invoice_services_never_bills_twice_and_cancel_releases(finance):
    uc = finance["use_case"]
    patient_id, services = await patient_with_unbilled(finance)
    first, rest = services[:1], services[1:]

    invoice = await uc.invoice_services(patient_id, InvoiceFromServicesDTO(
        services=refs(first), insurance_provider="Convênio Teste", coverage_percentage=Decimal(80)))
    assert invoice.status == BillingStatus.PENDING and invoice.items[0].source_id == first[0].source_id
    assert invoice.gross_total == first[0].price
    assert invoice.insurance_share == (first[0].price * Decimal("0.8")).quantize(Decimal("0.01"))
    assert invoice.allowed_actions == ["pagar", "cancelar"]

    remaining = {s.source_id for s in await uc.unbilled(patient_id)}
    assert first[0].source_id not in remaining and {s.source_id for s in rest} <= remaining
    with pytest.raises(ConflictError, match="já faturado"):
        await uc.invoice_services(patient_id, InvoiceFromServicesDTO(services=refs(first)))
    with pytest.raises(BusinessRuleViolation, match="convênio"):
        await uc.invoice_services(patient_id, InvoiceFromServicesDTO(services=refs(rest[:1]),
                                                                     coverage_percentage=Decimal(50)))

    await uc.cancel(invoice.id, "Paciente particular, não conveniado")
    assert first[0].source_id in {s.source_id for s in await uc.unbilled(patient_id)}  # volta a ser faturável

    published = [e.event_type for e in finance["events"].published]
    assert published == [EventType.INVOICE_ISSUED, EventType.INVOICE_CANCELLED]


async def test_payments_overdue_alert_and_summary(finance):
    session, uc, clock = finance["session"], finance["use_case"], finance["clock"]
    patient_id, services = await patient_with_unbilled(finance)
    invoice = await uc.invoice_services(patient_id, InvoiceFromServicesDTO(services=refs(services)))
    total = invoice.gross_total

    partial = await uc.register_payment(invoice.id, Decimal("10.00"), PaymentMethod.PIX, " entrada ")
    assert partial.status == BillingStatus.PARTIALLY_PAID and partial.payments[0].note == "entrada"
    assert partial.allowed_actions == ["pagar"]  # com pagamento, não cancela mais

    # Depois do vencimento: aparece como ATRASADO e a regra de alerta dispara.
    clock.now = SEED_NOW + timedelta(days=20)
    assert (await uc.detail(invoice.id)).status == BillingStatus.OVERDUE
    engine = AlertEngineUseCase(SQLAlchemySystemAlertRepository(session), SQLAlchemyAlertDetector(session),
                                InProcessPublisher(), clock=clock)
    opened = await engine.evaluate()
    alerts = [c for c in await SQLAlchemyAlertDetector(session).detect("FATURA_VENCIDA", clock.now)
              if c.subject_id == invoice.id]
    assert opened.opened >= 1 and len(alerts) == 1

    paid = await uc.register_payment(invoice.id, total - Decimal("10.00"), PaymentMethod.CARD, None)
    assert paid.status == BillingStatus.PAID and paid.balance == 0
    assert not [c for c in await SQLAlchemyAlertDetector(session).detect("FATURA_VENCIDA", clock.now)
                if c.subject_id == invoice.id]  # quitada: o alerta é resolvido na próxima avaliação

    summary = await uc.summary(SEED_NOW.date(), clock.now.date())
    assert summary.invoiced >= total and summary.received == await _payments_total(session, SEED_NOW, clock.now)
    assert sum(a.value for a in summary.invoiced_by_payer) == summary.invoiced
    assert [m.month for m in summary.monthly][-1] == f"{clock.now:%Y-%m}" and len(summary.monthly) == 6
    with pytest.raises(BusinessRuleViolation):
        await uc.summary(date(2026, 10, 2), date(2026, 10, 1))


async def _payments_total(session, start, end):
    total = await session.scalar(select(func.coalesce(func.sum(InvoicePaymentModel.amount), 0)).where(
        InvoicePaymentModel.paid_at >= start.replace(hour=0, minute=0),
        InvoicePaymentModel.paid_at < (end + timedelta(days=1)).replace(hour=0, minute=0)))
    return Decimal(str(total)).quantize(Decimal("0.01"))
