"""Financeiro ampliado: listagem, pagamentos parciais, cancelamento, faturamento de atendimentos e indicadores.

Complementa o BillingUseCase original (que continua atendendo às rotas antigas) e grava
apenas em tabelas novas — ver ADR-022.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable, Optional
import uuid

from app.application.dtos.common import Page
from app.application.dtos.finance_dto import (
    AmountByLabel, BillingItemDTO, FinanceSummaryDTO, InvoiceDetailDTO, InvoiceFromServicesDTO, InvoiceListItemDTO,
    MonthlyFinanceDTO, PaymentDTO, ServicePriceDTO, UnbilledServiceDTO,
)
from app.application.interfaces.billing_repository import BillingRepository
from app.application.interfaces.finance_queries import FinanceQueries, InvoiceFilter, InvoiceRow, ServicePrice
from app.application.services.events import EventPublisher, NullPublisher
from app.application.use_cases.dashboard_use_case import last_months
from app.domain.entities.billing import (
    CENTS, DEFAULT_EXAM_PRICE_CODE, OPEN_STATUSES, BillingItem, BillingStatus, Invoice, Payment, PaymentMethod,
    ServiceSource, format_brl,
)
from app.domain.events import DomainEvent, EventType
from app.domain.exceptions.common import BusinessRuleViolation, ConflictError, EntityNotFoundError

PRIVATE_PAYER = "Particular"
SUMMARY_MONTHS = 6


def zero() -> Decimal:
    return Decimal("0.00")


def new_invoice_number(now: datetime) -> str:
    return f"FAT-{now:%Y%m}-{uuid.uuid4().hex[:6].upper()}"


def overdue(row: InvoiceRow, now: datetime) -> bool:
    return row.status in OPEN_STATUSES and row.due_date is not None and row.due_date < now


def effective_status(row: InvoiceRow, now: datetime) -> BillingStatus:
    return BillingStatus.OVERDUE if overdue(row, now) else row.status


def insurance_share(gross: Decimal, coverage: Decimal) -> Decimal:
    return (gross * coverage / Decimal(100)).quantize(CENTS)


def ranked(amounts: dict[str, Decimal]) -> list[AmountByLabel]:
    return [AmountByLabel(label=k, value=v) for k, v in sorted(amounts.items(), key=lambda kv: -kv[1])]


def allowed_actions(invoice: Invoice) -> list[str]:
    if invoice.status == BillingStatus.DRAFT:
        return ["emitir", "cancelar"]
    if invoice.status in OPEN_STATUSES:
        return ["pagar"] if invoice.payments else ["pagar", "cancelar"]
    return []


class FinanceUseCase:
    def __init__(self, invoices: BillingRepository, queries: FinanceQueries,
                 events: EventPublisher = NullPublisher(), clock: Callable[[], datetime] = datetime.now):
        self.invoices = invoices
        self.queries = queries
        self.events = events
        self.clock = clock

    # ------------------------------------------------------------- consultas

    async def page(self, filters: InvoiceFilter, limit: int, offset: int) -> Page[InvoiceListItemDTO]:
        now = self.clock()
        rows, total = await self.queries.invoices(filters, now, limit, offset)
        return Page(items=[self._list_item(r, now) for r in rows], total=total, limit=limit, offset=offset)

    async def detail(self, invoice_id: uuid.UUID) -> InvoiceDetailDTO:
        return await self._detail(await self._get(invoice_id))

    async def prices(self) -> list[ServicePriceDTO]:
        return [ServicePriceDTO(**vars(p)) for p in (await self.queries.prices()).values()]

    async def unbilled(self, patient_id: uuid.UUID) -> list[UnbilledServiceDTO]:
        await self._patient_name(patient_id)
        prices = await self.queries.prices()
        result = []
        for service in await self.queries.unbilled_services(patient_id):
            price = self._price_for(prices, service.source_type, service.price_code)
            result.append(UnbilledServiceDTO(source_type=service.source_type, source_id=service.source_id,
                                             performed_at=service.performed_at, description=service.description,
                                             price_code=price.code, billing_type=price.billing_type, price=price.price))
        return result

    # --------------------------------------------------------------- comandos

    async def invoice_services(self, patient_id: uuid.UUID, request: InvoiceFromServicesDTO) -> InvoiceDetailDTO:
        """Cria uma fatura com consultas/exames ainda não faturados, ao preço da tabela vigente."""
        await self._patient_name(patient_id)
        available = {(s.source_type, s.source_id): s for s in await self.unbilled(patient_id)}
        requested = {(ref.source_type, ref.source_id) for ref in request.services}
        missing = requested - available.keys()
        if missing:
            raise ConflictError(f"{len(missing)} atendimento(s) já faturado(s), inexistente(s) ou de outro paciente.")

        now = self.clock()
        invoice = Invoice(patient_id=patient_id, invoice_number=new_invoice_number(now), issue_date=now,
                          insurance_provider=(request.insurance_provider or "").strip() or None,
                          insurance_policy_number=request.insurance_policy_number,
                          insurance_coverage_percentage=request.coverage_percentage)
        if invoice.insurance_coverage_percentage > 0 and not invoice.insurance_provider:
            raise BusinessRuleViolation("Informe o convênio para aplicar cobertura.")
        for key in sorted(requested, key=lambda k: available[k].performed_at):
            service = available[key]
            invoice.add_item(BillingItem(description=f"{service.description} ({service.performed_at:%d/%m/%Y})",
                                         billing_type=service.billing_type, quantity=Decimal(1),
                                         unit_price=service.price, source_type=service.source_type,
                                         source_id=service.source_id))
        if request.issue:
            invoice.issue(now)
        saved = await self.invoices.save_invoice(invoice)
        if request.issue:
            await self._publish(EventType.INVOICE_ISSUED, saved, f"Fatura {saved.invoice_number} emitida "
                                f"({format_brl(saved.calculate_gross_total())}).")
        return await self._detail(saved)

    async def issue(self, invoice_id: uuid.UUID) -> InvoiceDetailDTO:
        invoice = await self._get(invoice_id)
        invoice.issue(self.clock())
        await self.invoices.save_invoice(invoice)
        await self._publish(EventType.INVOICE_ISSUED, invoice, f"Fatura {invoice.invoice_number} emitida "
                            f"({format_brl(invoice.calculate_gross_total())}).")
        return await self._detail(invoice)

    async def register_payment(self, invoice_id: uuid.UUID, amount: Decimal, method: PaymentMethod,
                               note: Optional[str]) -> InvoiceDetailDTO:
        invoice = await self._get(invoice_id)
        payment = Payment(amount=amount, method=method, paid_at=self.clock(), note=(note or "").strip() or None)
        invoice.register_payment(payment)
        await self.invoices.save_invoice(invoice)
        await self._publish(EventType.PAYMENT_RECORDED, invoice,
                            f"Pagamento de {format_brl(payment.amount)} ({method.value}) na fatura {invoice.invoice_number}"
                            + (" — quitada." if invoice.status == BillingStatus.PAID else "."),
                            {"amount": str(payment.amount), "method": method.value, "status": invoice.status.value})
        return await self._detail(invoice)

    async def cancel(self, invoice_id: uuid.UUID, reason: str) -> InvoiceDetailDTO:
        invoice = await self._get(invoice_id)
        invoice.cancel(reason, self.clock())
        await self.invoices.save_invoice(invoice)
        await self._publish(EventType.INVOICE_CANCELLED, invoice,
                            f"Fatura {invoice.invoice_number} cancelada: {invoice.cancellation_reason}")
        return await self._detail(invoice)

    # ------------------------------------------------------------ indicadores

    async def summary(self, start: Optional[date] = None, end: Optional[date] = None) -> FinanceSummaryDTO:
        """Indicadores do período [start, end] (datas inclusivas; padrão: mês corrente) e série dos últimos meses."""
        end = end or self.clock().date()
        start = start or end.replace(day=1)
        if end < start:
            raise BusinessRuleViolation("A data final deve ser igual ou posterior à inicial.")
        now = self.clock()
        period = (datetime.combine(start, datetime.min.time()), datetime.combine(end + timedelta(days=1), datetime.min.time()))
        issued = await self.queries.issued_between(*period)
        valid = [r for r in issued if r.status != BillingStatus.CANCELLED]
        payments = await self.queries.payments_between(*period)
        open_rows = await self.queries.open_invoices()
        late = [r for r in open_rows if overdue(r, now)]

        by_method: dict[str, Decimal] = defaultdict(zero)
        for p in payments:
            by_method[p.method.value] += p.amount
        by_payer: dict[str, Decimal] = defaultdict(zero)
        for r in valid:
            covered = insurance_share(r.gross_total, r.coverage_percentage)
            if covered and r.insurance_provider:
                by_payer[r.insurance_provider] += covered
            by_payer[PRIVATE_PAYER] += r.gross_total - covered

        months = last_months(end, SUMMARY_MONTHS)
        history_start = datetime.combine(months[0], datetime.min.time())
        monthly_invoiced: dict[str, Decimal] = defaultdict(zero)
        for r in await self.queries.issued_between(history_start, period[1]):
            if r.status != BillingStatus.CANCELLED:
                monthly_invoiced[f"{r.issue_date:%Y-%m}"] += r.gross_total
        monthly_received: dict[str, Decimal] = defaultdict(zero)
        for p in await self.queries.payments_between(history_start, period[1]):
            monthly_received[f"{p.paid_at:%Y-%m}"] += p.amount

        return FinanceSummaryDTO(
            period_start=start, period_end=end,
            invoiced=sum((r.gross_total for r in valid), Decimal("0.00")),
            received=sum((p.amount for p in payments), Decimal("0.00")),
            receivable=sum((r.gross_total - r.amount_paid for r in open_rows), Decimal("0.00")),
            overdue=sum((r.gross_total - r.amount_paid for r in late), Decimal("0.00")),
            overdue_count=len(late), open_count=len(open_rows),
            invoices_by_status=dict(Counter(effective_status(r, now).value for r in issued)),
            received_by_method=ranked(by_method), invoiced_by_payer=ranked(by_payer),
            monthly=[MonthlyFinanceDTO(month=f"{m:%Y-%m}", invoiced=monthly_invoiced[f"{m:%Y-%m}"],
                                       received=monthly_received[f"{m:%Y-%m}"]) for m in months])

    # ---------------------------------------------------------------- apoio

    async def _get(self, invoice_id: uuid.UUID) -> Invoice:
        invoice = await self.invoices.get_invoice_by_id(invoice_id)
        if not invoice:
            raise EntityNotFoundError("Fatura", invoice_id)
        return invoice

    async def _patient_name(self, patient_id: uuid.UUID) -> str:
        name = await self.queries.patient_name(patient_id)
        if name is None:
            raise EntityNotFoundError("Paciente", patient_id)
        return name

    @staticmethod
    def _price_for(prices: dict[str, ServicePrice], source: ServiceSource, code: str) -> ServicePrice:
        price = prices.get(code) or (prices.get(DEFAULT_EXAM_PRICE_CODE) if source == ServiceSource.EXAM else None)
        if price is None:
            raise BusinessRuleViolation(f"Serviço sem preço na tabela: {code}.")
        return price

    def _list_item(self, r: InvoiceRow, now: datetime) -> InvoiceListItemDTO:
        return InvoiceListItemDTO(id=r.id, number=r.number, patient_id=r.patient_id, patient_name=r.patient_name,
                                  status=effective_status(r, now), issue_date=r.issue_date, due_date=r.due_date,
                                  gross_total=r.gross_total, amount_paid=r.amount_paid,
                                  balance=r.gross_total - r.amount_paid, insurance_provider=r.insurance_provider,
                                  coverage_percentage=r.coverage_percentage)

    async def _detail(self, invoice: Invoice) -> InvoiceDetailDTO:
        gross = invoice.calculate_gross_total().quantize(CENTS)
        covered = insurance_share(gross, Decimal(invoice.insurance_coverage_percentage))
        status = invoice.effective_status(self.clock())
        return InvoiceDetailDTO(
            id=invoice.id, number=invoice.invoice_number, patient_id=invoice.patient_id,
            patient_name=await self._patient_name(invoice.patient_id), status=status, issue_date=invoice.issue_date,
            due_date=invoice.due_date, gross_total=gross, amount_paid=invoice.amount_paid(), balance=invoice.balance(),
            insurance_provider=invoice.insurance_provider, coverage_percentage=invoice.insurance_coverage_percentage,
            insurance_policy_number=invoice.insurance_policy_number, insurance_share=covered,
            patient_share=gross - covered,
            items=[BillingItemDTO(id=i.id, description=i.description, billing_type=i.billing_type, quantity=i.quantity,
                                  unit_price=i.unit_price, discount=i.discount, total=i.calculate_total(),
                                  source_type=i.source_type, source_id=i.source_id) for i in invoice.items],
            payments=[PaymentDTO(id=p.id, amount=p.amount, method=p.method, paid_at=p.paid_at, note=p.note)
                      for p in invoice.payments],
            cancellation_reason=invoice.cancellation_reason, cancelled_at=invoice.cancelled_at, allowed_actions=allowed_actions(invoice))

    async def _publish(self, event_type: EventType, invoice: Invoice, summary: str, data: Optional[dict] = None) -> None:
        await self.events.publish(DomainEvent(event_type=event_type, occurred_at=self.clock(), entity_type="Fatura",
                                              entity_id=invoice.id, patient_id=invoice.patient_id, summary=summary,
                                              data={"number": invoice.invoice_number, **(data or {})}))
