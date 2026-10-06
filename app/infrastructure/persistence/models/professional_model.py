from datetime import datetime, time
from typing import List, Optional
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.models.user_model import Base


class DepartmentModel(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class SpecialtyModel(Base):
    __tablename__ = "specialties"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    default_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)


class ProfessionalModel(Base):
    __tablename__ = "professionals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    professional_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    registry_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    specialty_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("specialties.id"), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ATIVO", index=True)
    bio: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    working_hours: Mapped[List["WorkingHoursModel"]] = relationship(
        back_populates="professional", cascade="all, delete-orphan", lazy="selectin",
        order_by="(WorkingHoursModel.weekday, WorkingHoursModel.start_time)",
    )


class WorkingHoursModel(Base):
    __tablename__ = "professional_working_hours"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    professional_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    professional: Mapped[ProfessionalModel] = relationship(back_populates="working_hours")
