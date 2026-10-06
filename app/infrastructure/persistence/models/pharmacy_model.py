"""Tabelas da farmácia expandida. 'medications' e 'inventory_items' (legado) não são alteradas."""
from datetime import date, datetime
from typing import List, Optional
import uuid

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.models.user_model import Base


class MedicationCategoryModel(Base):
    __tablename__ = "medication_categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))


class MedicationDetailsModel(Base):
    __tablename__ = "medication_details"

    medication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medications.id", ondelete="CASCADE"), primary_key=True)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("medication_categories.id"), index=True)
    catalog_status: Mapped[str] = mapped_column(String(20), nullable=False, default="ATIVO")
    requires_prescription: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class StockLotModel(Base):
    __tablename__ = "stock_lots"
    __table_args__ = (
        UniqueConstraint("medication_id", "location", "lot_number", name="uq_stock_lot"),
        Index("ix_stock_lots_medication_location", "medication_id", "location"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    medication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medications.id"), nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    lot_number: Mapped[str] = mapped_column(String(40), nullable=False)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class InventoryMovementModel(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (Index("ix_movements_medication_occurred", "medication_id", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    medication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medications.id"), nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)
    lot_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("stock_lots.id"))
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(index=True)
    reason: Mapped[Optional[str]] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PrescriptionModel(Base):
    __tablename__ = "prescriptions"
    __table_args__ = (Index("ix_prescriptions_patient_issued", "patient_id", "issued_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    prescriber_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professionals.id"), nullable=False)
    appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("appointments.id"))
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    special_control: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allergy_override_reason: Mapped[Optional[str]] = mapped_column(String(500))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(500))

    items: Mapped[List["PrescriptionItemModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="PrescriptionItemModel.position")


class PrescriptionItemModel(Base):
    __tablename__ = "prescription_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    prescription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prescriptions.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    medication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medications.id"), nullable=False, index=True)
    dose: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    route: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    dispensed_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    instructions: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    status_reason: Mapped[Optional[str]] = mapped_column(String(500))


class DispensationModel(Base):
    __tablename__ = "dispensations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    prescription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prescriptions.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    pharmacist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professionals.id"), nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    dispensed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500))

    lines: Mapped[List["DispensationLineModel"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class DispensationLineModel(Base):
    __tablename__ = "dispensation_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dispensation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dispensations.id", ondelete="CASCADE"), index=True)
    prescription_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prescription_items.id"), nullable=False)
    medication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medications.id"), nullable=False)
    lot_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("stock_lots.id"))
    lot_number: Mapped[Optional[str]] = mapped_column(String(40))
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
