"""Tabelas do financeiro ampliado (ADR-022).

São todas novas e apenas referenciam `invoices`/`billing_items` por chave estrangeira:
as tabelas originais do faturamento não são alteradas.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.user_model import Base


class InvoicePaymentModel(Base):
    """Pagamentos (parciais ou totais) de uma fatura; registros só por acréscimo."""
    __tablename__ = "invoice_payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    note: Mapped[Optional[str]] = mapped_column(String(255))


class InvoiceCancellationModel(Base):
    __tablename__ = "invoice_cancellations"

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), primary_key=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    cancelled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class BillingItemSourceModel(Base):
    """Liga um item faturado ao atendimento de origem.

    Não há restrição única: se a fatura for cancelada, o atendimento volta a ser faturável. A regra
    "no máximo uma fatura não cancelada por atendimento" é verificada no caso de uso.
    """
    __tablename__ = "billing_item_sources"
    __table_args__ = (Index("ix_billing_item_sources_source", "source_type", "source_id"),)

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("billing_items.id"), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)


class ServicePriceModel(Base):
    """Tabela de preços fictícia usada para faturar consultas e exames."""
    __tablename__ = "service_prices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(160), nullable=False)
    billing_type: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
