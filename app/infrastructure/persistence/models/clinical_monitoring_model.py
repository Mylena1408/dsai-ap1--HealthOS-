"""Tabelas de sinais vitais e laboratório (todas novas, ADR-003)."""
from datetime import datetime
from typing import List, Optional
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.models.user_model import Base


class VitalSignsModel(Base):
    __tablename__ = "vital_signs"
    __table_args__ = (Index("ix_vital_signs_patient_recorded", "patient_id", "recorded_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    professional_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("professionals.id"), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    systolic: Mapped[Optional[int]] = mapped_column(Integer)
    diastolic: Mapped[Optional[int]] = mapped_column(Integer)
    heart_rate: Mapped[Optional[int]] = mapped_column(Integer)
    respiratory_rate: Mapped[Optional[int]] = mapped_column(Integer)
    temperature: Mapped[Optional[float]] = mapped_column(Float)
    oxygen_saturation: Mapped[Optional[int]] = mapped_column(Integer)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    height_cm: Mapped[Optional[float]] = mapped_column(Float)
    glucose_mg_dl: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(String(500))


class LaboratoryModel(Base):
    __tablename__ = "laboratories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(255))


class ExamTypeModel(Base):
    __tablename__ = "exam_types"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    sample_type: Mapped[str] = mapped_column(String(20), nullable=False)
    turnaround_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    preparation: Mapped[Optional[str]] = mapped_column(String(255))

    analytes: Mapped[List["AnalyteModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="AnalyteModel.position")


class AnalyteModel(Base):
    __tablename__ = "exam_analytes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    exam_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_types.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    decimals: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    plausible_min: Mapped[float] = mapped_column(Float, nullable=False)
    plausible_max: Mapped[float] = mapped_column(Float, nullable=False)
    normal_min: Mapped[Optional[float]] = mapped_column(Float)
    normal_max: Mapped[Optional[float]] = mapped_column(Float)
    critical_min: Mapped[Optional[float]] = mapped_column(Float)
    critical_max: Mapped[Optional[float]] = mapped_column(Float)


class ExamRequestModel(Base):
    __tablename__ = "exam_requests"
    __table_args__ = (Index("ix_exam_requests_patient_requested", "patient_id", "requested_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    exam_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_types.id"), nullable=False, index=True)
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("professionals.id"))
    appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("appointments.id"))
    laboratory_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("laboratories.id"))
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    clinical_indication: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sample_code: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    result_notes: Mapped[Optional[str]] = mapped_column(Text)
    resulted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    validated_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("professionals.id"))
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(500))

    results: Mapped[List["ExamResultModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="ExamResultModel.position")
    history: Mapped[List["ExamStatusHistoryModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="ExamStatusHistoryModel.changed_at")


class ExamResultModel(Base):
    __tablename__ = "exam_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    exam_request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_requests.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    analyte_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    analyte_name: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_text: Mapped[str] = mapped_column(String(60), nullable=False)
    flag: Mapped[str] = mapped_column(String(20), nullable=False)


class ExamStatusHistoryModel(Base):
    __tablename__ = "exam_request_status_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    exam_request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_requests.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(500))
