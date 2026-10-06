"""Prontuário eletrônico didático: perfil clínico, alergias, condições, diagnósticos e procedimentos.

Todas as informações são fictícias e servem apenas para demonstrar regras de
negócio; nada aqui representa orientação ou diagnóstico médico real.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional
import uuid

from app.domain.exceptions.common import BusinessRuleViolation, InvalidTransitionError

MAX_EMERGENCY_CONTACTS = 3


def _require_text(value: Optional[str], label: str, minimum: int = 2) -> str:
    text = (value or "").strip()
    if len(text) < minimum:
        raise BusinessRuleViolation(f"{label} deve ter pelo menos {minimum} caracteres.")
    return text


def _not_in_future(value: Optional[date], label: str, today: date) -> None:
    if value and value > today:
        raise BusinessRuleViolation(f"{label} não pode estar no futuro.")


# ----------------------------------------------------------------- perfil

class BloodType(Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"
    UNKNOWN = "NAO_INFORMADO"


@dataclass
class EmergencyContact:
    full_name: str
    relationship: str
    phone: str
    is_primary: bool = False
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        self.full_name = _require_text(self.full_name, "O nome do contato", 3)
        self.relationship = _require_text(self.relationship, "O parentesco")
        digits = [c for c in self.phone if c.isdigit()]
        if not 10 <= len(digits) <= 13:
            raise BusinessRuleViolation("O telefone do contato deve ter entre 10 e 13 dígitos.")


@dataclass
class PatientProfile:
    """Dados clínicos complementares do paciente (1:1 com a tabela legada 'patients')."""
    patient_id: uuid.UUID
    blood_type: BloodType = BloodType.UNKNOWN
    occupation: Optional[str] = None
    notes: Optional[str] = None
    emergency_contacts: list[EmergencyContact] = field(default_factory=list)
    updated_at: Optional[datetime] = None

    def add_contact(self, contact: EmergencyContact) -> None:
        if len(self.emergency_contacts) >= MAX_EMERGENCY_CONTACTS:
            raise BusinessRuleViolation(f"São permitidos no máximo {MAX_EMERGENCY_CONTACTS} contatos de emergência.")
        if contact.is_primary or not self.emergency_contacts:
            # Sempre existe exatamente um contato principal.
            for existing in self.emergency_contacts:
                existing.is_primary = False
            contact.is_primary = True
        self.emergency_contacts.append(contact)

    def remove_contact(self, contact_id: uuid.UUID) -> None:
        remaining = [c for c in self.emergency_contacts if c.id != contact_id]
        if len(remaining) == len(self.emergency_contacts):
            raise BusinessRuleViolation("Contato de emergência não encontrado para este paciente.")
        if remaining and not any(c.is_primary for c in remaining):
            remaining[0].is_primary = True
        self.emergency_contacts = remaining


# ---------------------------------------------------------------- alergias

class AllergyCategory(Enum):
    MEDICATION = "MEDICAMENTO"
    FOOD = "ALIMENTO"
    ENVIRONMENTAL = "AMBIENTAL"
    OTHER = "OUTRO"


class AllergySeverity(Enum):
    MILD = "LEVE"
    MODERATE = "MODERADA"
    SEVERE = "GRAVE"


class AllergyStatus(Enum):
    ACTIVE = "ATIVA"
    RESOLVED = "RESOLVIDA"


@dataclass
class Allergy:
    patient_id: uuid.UUID
    substance: str
    category: AllergyCategory
    severity: AllergySeverity
    reaction: Optional[str] = None
    status: AllergyStatus = AllergyStatus.ACTIVE
    recorded_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        self.substance = _require_text(self.substance, "A substância")

    def same_substance(self, other_substance: str) -> bool:
        return self.substance.casefold() == other_substance.strip().casefold()

    def resolve(self, now: datetime) -> None:
        if self.status == AllergyStatus.RESOLVED:
            raise InvalidTransitionError("Alergia", self.status.value, AllergyStatus.RESOLVED.value)
        self.status = AllergyStatus.RESOLVED
        self.resolved_at = now


# ------------------------------------------------------- condições clínicas

class ConditionStatus(Enum):
    ACTIVE = "ATIVA"
    CONTROLLED = "CONTROLADA"
    RESOLVED = "RESOLVIDA"


# Uma condição resolvida pode voltar a ficar ativa (recidiva).
CONDITION_TRANSITIONS = {
    ConditionStatus.ACTIVE: {ConditionStatus.CONTROLLED, ConditionStatus.RESOLVED},
    ConditionStatus.CONTROLLED: {ConditionStatus.ACTIVE, ConditionStatus.RESOLVED},
    ConditionStatus.RESOLVED: {ConditionStatus.ACTIVE},
}


@dataclass
class Condition:
    """Item da lista de problemas do paciente (ex.: hipertensão, asma)."""
    patient_id: uuid.UUID
    name: str
    code: Optional[str] = None  # código ilustrativo de classificação (ex.: CID-10)
    status: ConditionStatus = ConditionStatus.ACTIVE
    onset_date: Optional[date] = None
    resolved_date: Optional[date] = None
    notes: Optional[str] = None
    recorded_at: Optional[datetime] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        self.name = _require_text(self.name, "O nome da condição", 3)
        if self.onset_date and self.resolved_date and self.resolved_date < self.onset_date:
            raise BusinessRuleViolation("A data de resolução não pode ser anterior ao início.")

    def validate_dates(self, today: date) -> None:
        _not_in_future(self.onset_date, "O início da condição", today)
        _not_in_future(self.resolved_date, "A data de resolução", today)

    def change_status(self, target: ConditionStatus, today: date) -> None:
        if target not in CONDITION_TRANSITIONS[self.status]:
            raise InvalidTransitionError("Condição", self.status.value, target.value)
        if target == ConditionStatus.RESOLVED:
            if self.onset_date and today < self.onset_date:
                raise BusinessRuleViolation("A resolução não pode ser anterior ao início da condição.")
            self.resolved_date = today
        elif self.status == ConditionStatus.RESOLVED:
            self.resolved_date = None  # recidiva
        self.status = target


# --------------------------------------------------------------- diagnósticos

class DiagnosisType(Enum):
    PRIMARY = "PRINCIPAL"
    SECONDARY = "SECUNDARIO"


class DiagnosisCertainty(Enum):
    SUSPECTED = "SUSPEITA"
    CONFIRMED = "CONFIRMADA"
    RULED_OUT = "DESCARTADA"


@dataclass
class Diagnosis:
    """Hipótese diagnóstica registrada por um profissional (fictícia)."""
    patient_id: uuid.UUID
    description: str
    professional_id: Optional[uuid.UUID] = None
    appointment_id: Optional[uuid.UUID] = None
    code: Optional[str] = None
    diagnosis_type: DiagnosisType = DiagnosisType.PRIMARY
    certainty: DiagnosisCertainty = DiagnosisCertainty.SUSPECTED
    diagnosed_at: Optional[datetime] = None
    notes: Optional[str] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        self.description = _require_text(self.description, "A descrição do diagnóstico", 3)

    def confirm(self) -> None:
        self._resolve_certainty(DiagnosisCertainty.CONFIRMED)

    def rule_out(self) -> None:
        self._resolve_certainty(DiagnosisCertainty.RULED_OUT)

    def _resolve_certainty(self, target: DiagnosisCertainty) -> None:
        # Somente hipóteses (SUSPEITA) podem ser confirmadas ou descartadas.
        if self.certainty != DiagnosisCertainty.SUSPECTED:
            raise InvalidTransitionError("Diagnóstico", self.certainty.value, target.value)
        self.certainty = target


# --------------------------------------------------------------- procedimentos

@dataclass
class Procedure:
    patient_id: uuid.UUID
    name: str
    performed_at: datetime
    professional_id: Optional[uuid.UUID] = None
    appointment_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        self.name = _require_text(self.name, "O nome do procedimento", 3)

    def validate_date(self, now: datetime) -> None:
        if self.performed_at > now:
            raise BusinessRuleViolation("Um procedimento realizado não pode ter data futura.")
