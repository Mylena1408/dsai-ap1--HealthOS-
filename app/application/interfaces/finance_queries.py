"""Consultas de leitura do financeiro: listagens, indicadores e serviços ainda não faturados."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

from app.domain.entities.billing import BillingStatus, BillingType, PaymentMethod, ServiceSource


@dataclass(frozen=True)
class InvoiceFilter:
    status: Optional[BillingStatus] = None  # ATRASADO é avaliado pelo vencimento, não pelo valor gravado
    patient_id: Optional[uuid.UUID] = None
    issued_from: Optional[datetime] = None
    issued_until: Optional[datetime] = None
    number: Optional[str] = None


@dataclass(frozen=True)
class InvoiceRow:
    id: uuid.UUID
    number: str
    patient_id: uuid.UUID
    patient_name: str
    status: BillingStatus  # valor gravado
    issue_date: Optional[datetime]
    due_date: Optional[datetime]
    gross_total: Decimal
    amount_paid: Decimal
    insurance_provider: Optional[str]
    coverage_percentage: Decimal


@dataclass(frozen=True)
class PaymentRow:
    paid_at: datetime
    amount: Decimal
    method: PaymentMethod


@dataclass(frozen=True)
class UnbilledService:
    source_type: ServiceSource
    source_id: uuid.UUID
    performed_at: datetime
    description: str
    price_code: str


@dataclass(frozen=True)
class ServicePrice:
    code: str
    description: str
    billing_type: BillingType
    price: Decimal


class FinanceQueries(ABC):
    @abstractmethod
    async def invoices(self, filters: InvoiceFilter, now: datetime, limit: int, offset: int) -> tuple[list[InvoiceRow], int]:
        """Faturas filtradas, mais recentes primeiro, com totais calculados a partir dos itens e pagamentos."""

    @abstractmethod
    async def issued_between(self, start: datetime, end: datetime) -> list[InvoiceRow]:
        """Faturas emitidas no período (sem rascunhos)."""

    @abstractmethod
    async def open_invoices(self) -> list[InvoiceRow]:
        """Faturas com valor a receber, de qualquer data."""

    @abstractmethod
    async def payments_between(self, start: datetime, end: datetime) -> list[PaymentRow]: ...

    @abstractmethod
    async def unbilled_services(self, patient_id: uuid.UUID) -> list[UnbilledService]:
        """Consultas finalizadas e exames liberados sem item em fatura não cancelada."""

    @abstractmethod
    async def prices(self) -> dict[str, ServicePrice]:
        """Preços ativos por código."""

    @abstractmethod
    async def patient_name(self, patient_id: uuid.UUID) -> Optional[str]: ...
