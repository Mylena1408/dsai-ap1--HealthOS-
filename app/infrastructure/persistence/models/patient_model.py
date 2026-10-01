from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Date, func
from datetime import datetime, date
import uuid
from typing import Optional
from app.infrastructure.persistence.models.user_model import Base

class PatientModel(Base):
    """
    Modelo de persistência para a tabela 'patients'.
    Mapeia a entidade de domínio Patient para o banco de dados.
    """
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    cpf: Mapped[str] = mapped_column(String(14), unique=True, index=True, nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    insurance_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    insurance_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
