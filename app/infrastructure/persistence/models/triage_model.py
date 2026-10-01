from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, DateTime, Float, Integer, func
from datetime import datetime
import uuid
from app.infrastructure.persistence.models.user_model import Base

class TriageModel(Base):
    """
    Modelo de persistência para a tabela 'triages'.
    """
    __tablename__ = "triages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    triage_nurse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Prioridade (armazenada como string da cor: RED, ORANGE, etc)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Sinais Vitais
    blood_pressure: Mapped[str] = mapped_column(String(10), nullable=False, default="0/0")
    heart_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    oxygen_saturation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    respiratory_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Avaliação Clínica
    main_complaint: Mapped[str] = mapped_column(String(500), nullable=False)
    observations: Mapped[str] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
