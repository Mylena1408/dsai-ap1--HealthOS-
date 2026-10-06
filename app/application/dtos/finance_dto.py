from datetime import date, datetime
from decimal import Decimal
from typing import Optional
import uuid

from pydantic import BaseModel, Field, field_validator

from app.domain.entities.billing import BillingStatus, BillingType, PaymentMethod, ServiceSource


class InvoiceListItemDTO(BaseModel):
    id: uuid.UUID
    number: str
    patient_id: uuid.UUID
    patient_name: str
    status: BillingStatus  # situação efetiva (ATRASADO quando vencida e não quitada)
    issue_date: Optional[datetime]
    due_date: Optional[datetime]
    gross_total: Decimal
    amount_paid: Decimal
    balance: Decimal
    insurance_provider: Optional[str]
    coverage_percentage: Decimal


class BillingItemDTO(BaseModel):
    id: Optional[uuid.UUID]
    description: str
    billing_type: BillingType
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    total: Decimal
    source_type: Optional[ServiceSource]
    source_id: Optional[uuid.UUID]


class PaymentDTO(BaseModel):
    id: Optional[uuid.UUID]
    amount: Decimal
    method: PaymentMethod
    paid_at: datetime
    note: Optional[str]


class InvoiceDetailDTO(InvoiceListItemDTO):
    insurance_policy_number: Optional[str]
    insurance_share: Decimal
    patient_share: Decimal
    items: list[BillingItemDTO]
    payments: list[PaymentDTO]
    cancellation_reason: Optional[str]
    cancelled_at: Optional[datetime]
    allowed_actions: list[str]  # "emitir", "pagar", "cancelar"


class PaymentCreateDTO(BaseModel):
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    method: PaymentMethod
    note: Optional[str] = Field(None, max_length=255)

    @field_validator("method")
    @classmethod
    def method_must_be_known(cls, value: PaymentMethod) -> PaymentMethod:
        if value == PaymentMethod.UNSPECIFIED:
            raise ValueError("Informe a forma de pagamento.")
        return value


class InvoiceCancelDTO(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class ServiceRefDTO(BaseModel):
    source_type: ServiceSource
    source_id: uuid.UUID


class UnbilledServiceDTO(ServiceRefDTO):
    performed_at: datetime
    description: str
    price_code: str
    billing_type: BillingType
    price: Decimal


class InvoiceFromServicesDTO(BaseModel):
    services: list[ServiceRefDTO] = Field(..., min_length=1, max_length=50)
    insurance_provider: Optional[str] = Field(None, max_length=255)
    insurance_policy_number: Optional[str] = Field(None, max_length=100)
    coverage_percentage: Decimal = Field(Decimal("0"), ge=0, le=100, decimal_places=2)
    issue: bool = True  # emite já (PENDENTE) ou deixa em rascunho


class ServicePriceDTO(BaseModel):
    code: str
    description: str
    billing_type: BillingType
    price: Decimal


class AmountByLabel(BaseModel):
    label: str
    value: Decimal


class MonthlyFinanceDTO(BaseModel):
    month: str  # AAAA-MM
    invoiced: Decimal
    received: Decimal


class FinanceSummaryDTO(BaseModel):
    period_start: date
    period_end: date  # inclusivo
    invoiced: Decimal
    received: Decimal
    receivable: Decimal  # saldo em aberto de todas as faturas, de qualquer data
    overdue: Decimal
    overdue_count: int
    open_count: int
    invoices_by_status: dict[str, int]
    received_by_method: list[AmountByLabel]
    invoiced_by_payer: list[AmountByLabel]  # convênios x particular, pela cobertura de cada fatura
    monthly: list[MonthlyFinanceDTO]  # últimos 6 meses até o fim do período
    disclaimer: str = "Valores fictícios para demonstração."
