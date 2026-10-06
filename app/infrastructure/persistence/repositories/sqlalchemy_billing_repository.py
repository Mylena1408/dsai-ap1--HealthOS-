from typing import List, Optional
import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.domain.entities.billing import Invoice, BillingItem, BillingStatus, BillingType
from app.application.interfaces.billing_repository import BillingRepository
from app.infrastructure.persistence.models.billing_model import InvoiceModel, BillingItemModel

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

        return self._map_to_domain(db_invoice)

    async def get_invoices_by_patient(self, patient_id: uuid.UUID) -> List[Invoice]:
        stmt = (select(InvoiceModel).options(selectinload(InvoiceModel.items))
                .where(InvoiceModel.patient_id == patient_id))
        result = await self.session.execute(stmt)
        return [self._map_to_domain(i) for i in result.scalars().all()]

    async def update_invoice_status(self, invoice_id: uuid.UUID, status_value: str) -> bool:
        db_invoice = await self.session.get(InvoiceModel, invoice_id)
        if not db_invoice:
            return False

        db_invoice.status = status_value
        await self.session.flush()
        return True

    def _map_to_domain(self, db_invoice: InvoiceModel) -> Invoice:
        items = []
        for db_item in db_invoice.items:
            items.append(BillingItem(
                id=db_item.id,
                description=db_item.description,
                billing_type=BillingType(db_item.billing_type),
                quantity=Decimal(str(db_item.quantity)),
                unit_price=Decimal(str(db_item.unit_price)),
                discount=Decimal(str(db_item.discount))
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
            insurance_coverage_percentage=Decimal(str(db_invoice.insurance_coverage_percentage))
        )
