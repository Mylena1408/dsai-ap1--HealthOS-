from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, DateTime, Numeric, func
from datetime import datetime
import uuid
from typing import List
from app.infrastructure.persistence.models.user_model import Base

class InvoiceModel(Base):
    """
    Modelo de persistência para a tabela 'invoices'.
    """
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    issue_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")

    # Convênio
    insurance_provider: Mapped[str] = mapped_column(String(255), nullable=True)
    insurance_policy_number: Mapped[str] = mapped_column(String(100), nullable=True)
    insurance_coverage_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0.00)

    # Relacionamento com os itens da fatura
    items: Mapped[List["BillingItemModel"]] = relationship("BillingItemModel", back_populates="invoice", cascade="all, delete-orphan")

class BillingItemModel(Base):
    """
    Modelo de persistência para a tabela 'billing_items'.
    """
    __tablename__ = "billing_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_type: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=1.0)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0.00)

    invoice: Mapped["InvoiceModel"] = relationship("InvoiceModel", back_populates="items")
