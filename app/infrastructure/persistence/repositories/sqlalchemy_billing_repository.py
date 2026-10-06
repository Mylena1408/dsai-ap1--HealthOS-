from typing import List, Optional
import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.domain.entities.billing import (
    Invoice, BillingItem, BillingStatus, BillingType, Payment, PaymentMethod, ServiceSource,
)
from app.application.interfaces.billing_repository import BillingRepository
from app.infrastructure.persistence.models.billing_model import InvoiceModel, BillingItemModel
from app.infrastructure.persistence.models.finance_model import (
    BillingItemSourceModel, InvoiceCancellationModel, InvoicePaymentModel,
)

class SQLAlchemyBillingRepository(BillingRepository):
    """
    Implementação do BillingRepository utilizando SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_invoice(self, invoice: Invoice) -> Invoice:
        # Faturas existentes são atualizadas no lugar; os itens são carregados
        # antecipadamente porque o lazy loading não funciona em sessões assíncronas.
        db_invoice = None
        if invoice.id:
            result = await self.session.execute(
                select(InvoiceModel).options(selectinload(InvoiceModel.items))
                .where(InvoiceModel.id == invoice.id)
            )
            db_invoice = result.scalar_one_or_none()
        if db_invoice is None:
            db_invoice = InvoiceModel(id=invoice.id or uuid.uuid4(), items=[])
            self.session.add(db_invoice)

        db_invoice.patient_id = invoice.patient_id
        db_invoice.invoice_number = invoice.invoice_number
        db_invoice.issue_date = invoice.issue_date
        db_invoice.due_date = invoice.due_date
        db_invoice.status = invoice.status.value
        db_invoice.insurance_provider = invoice.insurance_provider
        db_invoice.insurance_policy_number = invoice.insurance_policy_number
        db_invoice.insurance_coverage_percentage = invoice.insurance_coverage_percentage

        existing_ids = {db_item.id for db_item in db_invoice.items}
        new_sources = []
        for item in invoice.items:
            if item.id in existing_ids:
                continue
            item.id = item.id or uuid.uuid4()
            db_invoice.items.append(BillingItemModel(
                id=item.id,
                description=item.description,
                billing_type=item.billing_type.value,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount=item.discount
            ))
            if item.source_type and item.source_id:
                new_sources.append(BillingItemSourceModel(item_id=item.id, source_type=item.source_type.value,
                                                          source_id=item.source_id))
        await self.session.flush()  # os itens precisam existir antes das origens que os referenciam
        self.session.add_all(new_sources)

        # Pagamentos só por acréscimo: os que ainda não têm id são novos.
        for payment in invoice.payments:
            if payment.id is None:
                payment.id = uuid.uuid4()
                self.session.add(InvoicePaymentModel(id=payment.id, invoice_id=db_invoice.id, amount=payment.amount,
                                                     method=payment.method.value, paid_at=payment.paid_at,
                                                     note=payment.note))
        if invoice.cancellation_reason and not await self.session.get(InvoiceCancellationModel, db_invoice.id):
            self.session.add(InvoiceCancellationModel(invoice_id=db_invoice.id, reason=invoice.cancellation_reason,
                                                      cancelled_at=invoice.cancelled_at))

        await self.session.flush()

        invoice.id = db_invoice.id
        return invoice

    async def get_invoice_by_id(self, invoice_id: uuid.UUID) -> Optional[Invoice]:
        stmt = (select(InvoiceModel).options(selectinload(InvoiceModel.items))
                .where(InvoiceModel.id == invoice_id))
        result = await self.session.execute(stmt)
        db_invoice = result.scalar_one_or_none()

        if not db_invoice:
            return None

        return (await self._map_all([db_invoice]))[0]

    async def get_invoices_by_patient(self, patient_id: uuid.UUID) -> List[Invoice]:
        stmt = (select(InvoiceModel).options(selectinload(InvoiceModel.items))
                .where(InvoiceModel.patient_id == patient_id))
        result = await self.session.execute(stmt)
        return await self._map_all(list(result.scalars().all()))

    async def update_invoice_status(self, invoice_id: uuid.UUID, status_value: str) -> bool:
        db_invoice = await self.session.get(InvoiceModel, invoice_id)
        if not db_invoice:
            return False

        db_invoice.status = status_value
        await self.session.flush()
        return True

    async def _map_all(self, db_invoices: List[InvoiceModel]) -> List[Invoice]:
        """Carrega pagamentos, cancelamentos e origens de todas as faturas em poucas consultas."""
        ids = [i.id for i in db_invoices]
        item_ids = [item.id for i in db_invoices for item in i.items]
        payments: dict = {}
        for p in await self.session.scalars(select(InvoicePaymentModel).where(InvoicePaymentModel.invoice_id.in_(ids))
                                            .order_by(InvoicePaymentModel.paid_at)):
            payments.setdefault(p.invoice_id, []).append(Payment(
                id=p.id, amount=Decimal(str(p.amount)), method=PaymentMethod(p.method), paid_at=p.paid_at, note=p.note))
        cancellations = {c.invoice_id: c for c in await self.session.scalars(
            select(InvoiceCancellationModel).where(InvoiceCancellationModel.invoice_id.in_(ids)))}
        sources = {s.item_id: s for s in await self.session.scalars(
            select(BillingItemSourceModel).where(BillingItemSourceModel.item_id.in_(item_ids)))}
        return [self._map_to_domain(i, payments.get(i.id, []), cancellations.get(i.id), sources) for i in db_invoices]

    def _map_to_domain(self, db_invoice: InvoiceModel, payments=(), cancellation=None, sources=None) -> Invoice:
        sources = sources or {}
        items = []
        for db_item in db_invoice.items:
            source = sources.get(db_item.id)
            items.append(BillingItem(
                id=db_item.id,
                description=db_item.description,
                billing_type=BillingType(db_item.billing_type),
                quantity=Decimal(str(db_item.quantity)),
                unit_price=Decimal(str(db_item.unit_price)),
                discount=Decimal(str(db_item.discount)),
                source_type=ServiceSource(source.source_type) if source else None,
                source_id=source.source_id if source else None,
            ))

        return Invoice(
            id=db_invoice.id,
            patient_id=db_invoice.patient_id,
            invoice_number=db_invoice.invoice_number,
            issue_date=db_invoice.issue_date,
            due_date=db_invoice.due_date,
            status=BillingStatus(db_invoice.status),
            items=items,
            insurance_provider=db_invoice.insurance_provider,
            insurance_policy_number=db_invoice.insurance_policy_number,
            insurance_coverage_percentage=Decimal(str(db_invoice.insurance_coverage_percentage)),
            payments=list(payments),
            cancellation_reason=cancellation.reason if cancellation else None,
            cancelled_at=cancellation.cancelled_at if cancellation else None,
        )
