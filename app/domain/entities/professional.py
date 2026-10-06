from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Optional
import uuid

from app.domain.exceptions.common import BusinessRuleViolation


class ProfessionalType(Enum):
    DOCTOR = "MEDICO"
    NURSE = "ENFERMEIRO"
    PHARMACIST = "FARMACEUTICO"
    NUTRITIONIST = "NUTRICIONISTA"
    PHYSIOTHERAPIST = "FISIOTERAPEUTA"
    PSYCHOLOGIST = "PSICOLOGO"
    OTHER = "OUTRO"


# Conselho de classe usado no registro fictício de cada tipo de profissional.
REGISTRY_COUNCIL = {
    ProfessionalType.DOCTOR: "CRM",
    ProfessionalType.NURSE: "COREN",
    ProfessionalType.PHARMACIST: "CRF",
    ProfessionalType.NUTRITIONIST: "CRN",
    ProfessionalType.PHYSIOTHERAPIST: "CREFITO",
    ProfessionalType.PSYCHOLOGIST: "CRP",
    ProfessionalType.OTHER: "REG",
}


class ProfessionalStatus(Enum):
    ACTIVE = "ATIVO"
    ON_LEAVE = "AFASTADO"
    INACTIVE = "INATIVO"


@dataclass
class Department:
    name: str
    description: Optional[str] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        if len(self.name.strip()) < 3:
            raise BusinessRuleViolation("O nome do departamento deve ter pelo menos 3 caracteres.")


@dataclass
class Specialty:
    name: str
    description: Optional[str] = None
    default_duration_minutes: int = 30
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        if len(self.name.strip()) < 3:
            raise BusinessRuleViolation("O nome da especialidade deve ter pelo menos 3 caracteres.")
        if not 10 <= self.default_duration_minutes <= 240:
            raise BusinessRuleViolation("A duração padrão deve estar entre 10 e 240 minutos.")


@dataclass
class WorkingHours:
    """Janela semanal de atendimento (weekday: 0 = segunda ... 6 = domingo)."""
    weekday: int
    start_time: time
    end_time: time
    professional_id: Optional[uuid.UUID] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        if not 0 <= self.weekday <= 6:
            raise BusinessRuleViolation("O dia da semana deve estar entre 0 (segunda) e 6 (domingo).")
        if self.start_time >= self.end_time:
            raise BusinessRuleViolation("O início do expediente deve ser anterior ao fim.")

    def covers(self, start: datetime, end: datetime) -> bool:
        """Indica se o intervalo [start, end) cabe inteiramente nesta janela."""
        return (start.weekday() == self.weekday and start.date() == end.date()
                and self.start_time <= start.time() and end.time() <= self.end_time)

    def overlaps(self, other: "WorkingHours") -> bool:
        return (self.weekday == other.weekday
                and self.start_time < other.end_time and other.start_time < self.end_time)


@dataclass
class Professional:
    """Profissional de saúde fictício da demonstração."""
    full_name: str
    professional_type: ProfessionalType
    registry_number: str
    department_id: Optional[uuid.UUID] = None
    specialty_id: Optional[uuid.UUID] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: ProfessionalStatus = ProfessionalStatus.ACTIVE
    bio: Optional[str] = None
    working_hours: list[WorkingHours] = field(default_factory=list)
    id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if len(self.full_name.strip()) < 3:
            raise BusinessRuleViolation("O nome do profissional deve ter pelo menos 3 caracteres.")
        if not self.registry_number.strip():
            raise BusinessRuleViolation("O registro profissional é obrigatório.")

    @property
    def is_available_for_booking(self) -> bool:
        return self.status == ProfessionalStatus.ACTIVE

    def set_working_hours(self, hours: list[WorkingHours]) -> None:
        """Substitui a grade semanal, rejeitando janelas sobrepostas no mesmo dia."""
        for i, current in enumerate(hours):
            for other in hours[i + 1:]:
                if current.overlaps(other):
                    raise BusinessRuleViolation(
                        f"Janelas de atendimento sobrepostas no dia {current.weekday}."
                    )
        self.working_hours = sorted(hours, key=lambda h: (h.weekday, h.start_time))

    def works_during(self, start: datetime, end: datetime) -> bool:
        return any(window.covers(start, end) for window in self.working_hours)
