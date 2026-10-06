"""Consulta (agendamento clínico) e sua máquina de estados.

    AGENDADA ──► CONFIRMADA ──► EM_ANDAMENTO ──► FINALIZADA
       │  │          │  │
       │  └──────────┼──┴──► NAO_COMPARECEU   (somente após o horário marcado)
       └─────────────┴─────► CANCELADA        (somente antes do horário marcado)

FINALIZADA, CANCELADA e NAO_COMPARECEU são estados finais.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import uuid

from app.domain.exceptions.common import BusinessRuleViolation, InvalidTransitionError


class AppointmentStatus(Enum):
    SCHEDULED = "AGENDADA"
    CONFIRMED = "CONFIRMADA"
    IN_PROGRESS = "EM_ANDAMENTO"
    COMPLETED = "FINALIZADA"
    CANCELLED = "CANCELADA"
    NO_SHOW = "NAO_COMPARECEU"


class AppointmentType(Enum):
    FIRST_VISIT = "PRIMEIRA_CONSULTA"
    FOLLOW_UP = "RETORNO"
    URGENT = "URGENCIA"
    TELEMEDICINE = "TELECONSULTA"


ALLOWED_TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.SCHEDULED: {AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW},
    AppointmentStatus.CONFIRMED: {AppointmentStatus.IN_PROGRESS, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW},
    AppointmentStatus.IN_PROGRESS: {AppointmentStatus.COMPLETED},
    AppointmentStatus.COMPLETED: set(),
    AppointmentStatus.CANCELLED: set(),
    AppointmentStatus.NO_SHOW: set(),
}

# Estados que ocupam a agenda do profissional e do paciente.
ACTIVE_STATUSES = frozenset({AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED, AppointmentStatus.IN_PROGRESS})

MIN_DURATION, MAX_DURATION = 10, 240
# Antecedência máxima para iniciar o atendimento antes do horário marcado.
EARLY_START_TOLERANCE = timedelta(minutes=30)


@dataclass
class StatusChange:
    from_status: Optional[AppointmentStatus]
    to_status: AppointmentStatus
    changed_at: datetime
    note: Optional[str] = None
    id: Optional[uuid.UUID] = None  # preenchido quando o registro é persistido


@dataclass
class Appointment:
    patient_id: uuid.UUID
    professional_id: uuid.UUID
    start_time: datetime
    duration_minutes: int
    appointment_type: AppointmentType = AppointmentType.FIRST_VISIT
    specialty_id: Optional[uuid.UUID] = None
    status: AppointmentStatus = AppointmentStatus.SCHEDULED
    reason: Optional[str] = None
    notes: Optional[str] = None
    cancellation_reason: Optional[str] = None
    history: list[StatusChange] = field(default_factory=list)
    id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        self._validate_duration(self.duration_minutes)

    @staticmethod
    def _validate_duration(minutes: int) -> None:
        if not MIN_DURATION <= minutes <= MAX_DURATION or minutes % 5:
            raise BusinessRuleViolation(
                f"A duração deve ser múltipla de 5 e estar entre {MIN_DURATION} e {MAX_DURATION} minutos."
            )

    @property
    def end_time(self) -> datetime:
        return self.start_time + timedelta(minutes=self.duration_minutes)

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def allowed_transitions(self, now: datetime) -> list[AppointmentStatus]:
        """Transições possíveis agora, considerando também as regras de horário."""
        allowed = []
        for target in ALLOWED_TRANSITIONS[self.status]:
            try:
                self._check_time_rules(target, now)
            except BusinessRuleViolation:
                continue
            allowed.append(target)
        return sorted(allowed, key=lambda s: list(AppointmentStatus).index(s))

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return self.start_time < end and start < self.end_time

    # ------------------------------------------------------------ transições

    def register_creation(self, now: datetime) -> None:
        """Primeiro registro do histórico, gravado quando a consulta é agendada."""
        self._record(None, AppointmentStatus.SCHEDULED, now, "Consulta agendada")

    def confirm(self, now: datetime) -> None:
        self._transition(AppointmentStatus.CONFIRMED, now)

    def start(self, now: datetime) -> None:
        self._transition(AppointmentStatus.IN_PROGRESS, now)

    def complete(self, now: datetime, notes: Optional[str] = None) -> None:
        self._transition(AppointmentStatus.COMPLETED, now)
        if notes:
            self.notes = notes

    def cancel(self, now: datetime, reason: str) -> None:
        if not reason or len(reason.strip()) < 3:
            raise BusinessRuleViolation("Informe o motivo do cancelamento (mínimo de 3 caracteres).")
        self._transition(AppointmentStatus.CANCELLED, now, note=reason)
        self.cancellation_reason = reason

    def mark_no_show(self, now: datetime) -> None:
        self._transition(AppointmentStatus.NO_SHOW, now)

    def reschedule(self, new_start: datetime, now: datetime, duration_minutes: Optional[int] = None) -> None:
        """Remarca uma consulta ainda não iniciada; ela volta a precisar de confirmação."""
        if self.status not in (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED):
            raise InvalidTransitionError("Consulta", self.status.value, "REMARCADA")
        if new_start <= now:
            raise BusinessRuleViolation("A nova data da consulta deve estar no futuro.")
        if duration_minutes is not None:
            self._validate_duration(duration_minutes)
            self.duration_minutes = duration_minutes
        previous = self.start_time
        self.start_time = new_start
        self._record(self.status, AppointmentStatus.SCHEDULED, now,
                     note=f"Remarcada de {previous:%d/%m/%Y %H:%M} para {new_start:%d/%m/%Y %H:%M}")
        self.status = AppointmentStatus.SCHEDULED

    # --------------------------------------------------------------- interno

    def _check_time_rules(self, target: AppointmentStatus, now: datetime) -> None:
        if target == AppointmentStatus.CANCELLED and now >= self.start_time:
            raise BusinessRuleViolation("Não é possível cancelar uma consulta cujo horário já começou.")
        if target == AppointmentStatus.NO_SHOW and now < self.start_time:
            raise BusinessRuleViolation("O não comparecimento só pode ser registrado após o horário da consulta.")
        if target == AppointmentStatus.IN_PROGRESS and now < self.start_time - EARLY_START_TOLERANCE:
            raise BusinessRuleViolation("O atendimento só pode ser iniciado até 30 minutos antes do horário marcado.")

    def _transition(self, target: AppointmentStatus, now: datetime, note: Optional[str] = None) -> None:
        if target not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidTransitionError("Consulta", self.status.value, target.value)
        self._check_time_rules(target, now)
        self._record(self.status, target, now, note)
        self.status = target

    def _record(self, from_status, to_status, now, note=None) -> None:
        self.history.append(StatusChange(from_status, to_status, now, note))
        self.updated_at = now
