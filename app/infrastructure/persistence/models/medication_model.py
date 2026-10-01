from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, DateTime, Float, Boolean, func
from datetime import datetime
import uuid
from app.infrastructure.persistence.models.user_model import Base

class MedicationModel(Base):
    """
    Modelo de persistência para a tabela 'medications'.
    """
    __tablename__ = "medications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    generic_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dosage: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    is_controlled_substance: Mapped[bool] = mapped_column(Boolean, default=False)
    manufacturer: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class InventoryItemModel(Base):
    """
    Modelo de persistência para a tabela 'inventory_items'.
    """
    __tablename__ = "inventory_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    medication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medications.id"), nullable=False, index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(String(100), nullable=False, index=True) # ID da ala/farmácia
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    min_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    max_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=1000.0)
    expiration_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
