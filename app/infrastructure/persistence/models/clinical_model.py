from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, DateTime, Text, func
from datetime import datetime
import uuid
from app.infrastructure.persistence.models.user_model import Base

class ClinicalNoteModel(Base):
    """
    Modelo de persistência para a tabela 'clinical_notes'.
    """
    __tablename__ = "clinical_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
