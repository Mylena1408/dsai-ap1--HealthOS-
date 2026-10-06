"""Tabelas do prontuário. Todas são novas e apenas referenciam 'patients' (ADR-003)."""
from datetime import date, datetime
from typing import List, Optional
import uuid

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.models.user_model import Base


class PatientProfileModel(Base):
    __tablename__ = "patient_profiles"

    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True)
    blood_type: Mapped[str] = mapped_column(String(15), nullable=False, default="NAO_INFORMADO")
    occupation: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    emergency_contacts: Mapped[List["EmergencyContactModel"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="EmergencyContactModel.full_name")


class EmergencyContactModel(Base):
    __tablename__ = "patient_emergency_contacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patient_profiles.patient_id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Atributo 'kinship' (coluna 'relationship') para não sombrear sqlalchemy.orm.relationship.
    kinship: Mapped[str] = mapped_column("relationship", String(50), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AllergyModel(Base):
    __tablename__ = "patient_allergies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    substance: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    reaction: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ATIVA")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ConditionModel(Base):
    __tablename__ = "patient_conditions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ATIVA")
    onset_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    resolved_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class DiagnosisModel(Base):
    __tablename__ = "patient_diagnoses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    professional_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("professionals.id"), nullable=True)
    appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("appointments.id"), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    diagnosis_type: Mapped[str] = mapped_column(String(20), nullable=False)
    certainty: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diagnosed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class ProcedureModel(Base):
    __tablename__ = "patient_procedures"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    professional_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("professionals.id"), nullable=True)
    appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("appointments.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
