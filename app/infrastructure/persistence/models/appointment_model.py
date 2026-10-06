from datetime import datetime
from typing import List, Optional
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.models.user_model import Base


class AppointmentModel(Base):
    """Consultas do módulo de agendamento clínico (independente da tabela legada 'schedules')."""
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_professional_start", "professional_id", "start_time"),
        Index("ix_appointments_patient_start", "patient_id", "start_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    professional_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professionals.id"), nullable=False)
    specialty_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("specialties.id"), nullable=True)
    appointment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # end_time é redundante com start + duração, mas permite filtrar sobreposições no banco.
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Timestamps gerados no Python (e não pelo banco): valores gerados pelo servidor ficam
    # expirados após o flush e recarregá-los exigiria I/O implícito na sessão assíncrona.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    history: Mapped[List["AppointmentStatusHistoryModel"]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan", lazy="selectin",
        order_by="AppointmentStatusHistoryModel.changed_at",
    )


class AppointmentStatusHistoryModel(Base):
    __tablename__ = "appointment_status_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    appointment: Mapped[AppointmentModel] = relationship(back_populates="history")
