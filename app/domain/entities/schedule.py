from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Optional, List
import uuid

class ScheduleStatus(Enum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    BLOCKED = "BLOCKED"
    CANCELED = "CANCELED"

class ShiftType(Enum):
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    NIGHT = "NIGHT"
    FULL_DAY = "FULL_DAY"

@dataclass
class Schedule:
    """
    Entidade de Domínio Schedule.
    Representa a disponibilidade de um profissional de saúde em um determinado horário.

    Esta entidade foca na gestão de slots temporais, garantindo que não haja
    sobreposição de horários para o mesmo profissional.
    """
    id: Optional[uuid.UUID] = None
    doctor_id: uuid.UUID = field(default=None)
    start_time: datetime = field(default=None)
    end_time: datetime = field(default=None)
    status: ScheduleStatus = ScheduleStatus.AVAILABLE
    patient_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self.validate_times()

    def validate_times(self):
        """Validação rigorosa de lógica temporal para evitar inconsistências."""
        if not self.start_time or not self.end_time:
            raise ValueError("Start time and end time are required.")

        if self.start_time >= self.end_time:
            raise ValueError("Start time must be before end time.")

        duration = self.end_time - self.start_time
        if duration < timedelta(minutes=15):
            raise ValueError("Minimum schedule slot duration is 15 minutes.")

        if duration > timedelta(hours=12):
            raise ValueError("Maximum schedule slot duration is 12 hours.")

    def book(self, patient_id: uuid.UUID):
        """Transição de estado para Reservado."""
        if self.status != ScheduleStatus.AVAILABLE:
            raise ValueError(f"Schedule slot is not available. Current status: {self.status.value}")

        self.patient_id = patient_id
        self.status = ScheduleStatus.BOOKED
        self.updated_at = datetime.now()

    def cancel(self):
        """Transição de estado para Cancelado."""
        if self.status == ScheduleStatus.AVAILABLE:
            raise ValueError("Cannot cancel an available slot.")

        self.status = ScheduleStatus.CANCELED
        self.updated_at = datetime.now()

    def block(self):
        """Bloqueia o horário para manutenção ou folga."""
        self.status = ScheduleStatus.BLOCKED
        self.patient_id = None
        self.updated_at = datetime.now()

    def release(self):
        """Torna o horário disponível novamente."""
        self.status = ScheduleStatus.AVAILABLE
        self.patient_id = None
        self.updated_at = datetime.now()
