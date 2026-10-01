from typing import List, Optional
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from app.application.interfaces.billing_repository import BillingRepository
from app.domain.entities.billing import Invoice, BillingItem, BillingStatus, BillingType
from app.domain.exceptions.base import DomainException

class BillingUseCase:
    """
    Caso de Uso para a gestão de faturamento hospitalar.
    Orquestra a criação de faturas, adição de custos de atendimento e
    processamento de pagamentos via convênios e particular.
    """

    def __init__(self, billing_repository: BillingRepository):
        self.billing_repository = billing_repository

    async def create_invoice(self, patient_id: uuid.UUID,
                             invoice_number: str,
                             insurance_provider: Optional[str] = None,
                             insurance_policy_number: Optional[str] = None,
                             insurance_coverage: Decimal = Decimal("0.00")) -> Invoice:
        """
        Inicia uma nova fatura para um paciente.
        """
        invoice = Invoice(
            patient_id=patient_id,
            invoice_number=invoice_number,
            insurance_provider=insurance_provider,
            insurance_policy_number=insurance_policy_number,
            insurance_coverage_percentage=insurance_coverage,
            status=BillingStatus.DRAFT
        )
        return await self.billing_repository.save_invoice(invoice)

    async def add_charge_to_invoice(self, invoice_id: uuid.UUID,
                                   description: str,
                                   billing_type: BillingType,
                                   quantity: Decimal,
                                   unit_price: Decimal,
                                   discount: Decimal = Decimal("0.00")) -> Invoice:
        """
        Adiciona um item de custo a uma fatura existente.
        """
        invoice = await self.billing_repository.get_invoice_by_id(invoice_id)
        if not invoice:
            raise DomainException(message="Fatura não encontrada.")

        item = BillingItem(
            description=description,
            billing_type=billing_type,
            quantity=quantity,
            unit_price=unit_price,
            discount=discount
        )

        try:
            invoice.add_item(item)
        except ValueError as e:
            raise DomainException(message=str(e))

        return await self.billing_repository.save_invoice(invoice)

    async def finalize_invoice(self, invoice_id: uuid.UUID) -> Invoice:
        """
        Fecha a fatura para cobrança, mudando o status de DRAFT para PENDING.
        """
        invoice = await self.billing_repository.get_invoice_by_id(invoice_id)
        if not invoice:
            raise DomainException(message="Fatura não encontrada.")

        if not invoice.items:
            raise DomainException(message="Não é possível finalizar uma fatura sem itens de cobrança.")

        invoice.status = BillingStatus.PENDING
        # Define a data de vencimento para 15 dias a partir de hoje
        invoice.due_date = datetime.now() + timedelta(days=15)

        return await self.billing_repository.save_invoice(invoice)

    async def record_payment(self, invoice_id: uuid.UUID) -> Invoice:
        """
        Registra o pagamento total da fatura.
        """
        invoice = await self.billing_repository.get_invoice_by_id(invoice_id)
        if not invoice:
            raise DomainException(message="Fatura não encontrada.")

        if invoice.status == BillingStatus.PAID:
            raise DomainException(message="Esta fatura já está paga.")

        invoice.mark_as_paid()
        return await self.billing_repository.save_invoice(invoice)

    async def get_patient_financial_summary(self, patient_id: uuid.UUID) -> List[dict]:
        """
        Gera um resumo financeiro de todas as faturas de um paciente.
        """
        invoices = await self.billing_repository.get_invoices_by_patient(patient_id)
        summary = []

        for inv in invoices:
            summary.append({
                "invoice_id": inv.id,
                "number": inv.invoice_number,
                "gross_total": inv.calculate_gross_total(),
                "patient_share": inv.calculate_patient_share(),
                "status": inv.status.value,
                "due_date": inv.due_date
            })

        return summary
