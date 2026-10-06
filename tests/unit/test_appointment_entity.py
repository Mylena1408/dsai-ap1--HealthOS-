from datetime import datetime, time, timedelta
import uuid

import pytest

from app.domain.entities.appointment import Appointment, AppointmentStatus as S
from app.domain.entities.professional import Professional, ProfessionalType, WorkingHours
from app.domain.exceptions.common import BusinessRuleViolation, InvalidTransitionError

START = datetime(2026, 11, 10, 9, 0)  # terça-feira
BEFORE = START - timedelta(days=1)
AFTER = START + timedelta(hours=1)


def make(status=S.SCHEDULED, duration=30) -> Appointment:
    return Appointment(patient_id=uuid.uuid4(), professional_id=uuid.uuid4(),
                       start_time=START, duration_minutes=duration, status=status)


def test_happy_path_records_every_transition():
    appt = make()
    appt.confirm(BEFORE)
    appt.start(START)
    appt.complete(AFTER, notes="Retorno em 30 dias (fictício)")

    assert appt.status == S.COMPLETED
    assert appt.notes.startswith("Retorno")
    assert [(h.from_status, h.to_status) for h in appt.history] == [
        (S.SCHEDULED, S.CONFIRMED), (S.CONFIRMED, S.IN_PROGRESS), (S.IN_PROGRESS, S.COMPLETED),
    ]


@pytest.mark.parametrize("status,action", [
    (S.CANCELLED, lambda a: a.start(START)),           # Cancelada -> Em andamento
    (S.CANCELLED, lambda a: a.confirm(BEFORE)),
    (S.COMPLETED, lambda a: a.cancel(BEFORE, "motivo")),
    (S.NO_SHOW, lambda a: a.confirm(BEFORE)),
    (S.SCHEDULED, lambda a: a.complete(AFTER)),        # precisa passar por Em andamento
    (S.IN_PROGRESS, lambda a: a.cancel(BEFORE, "motivo")),
])
def test_incoherent_transitions_are_rejected(status, action):
    appt = make(status)
    with pytest.raises(InvalidTransitionError):
        action(appt)
    assert appt.status == status
    assert appt.history == []


def test_time_rules():
    appt = make(S.CONFIRMED)
    with pytest.raises(BusinessRuleViolation):
        appt.cancel(START + timedelta(minutes=1), "tarde demais")
    with pytest.raises(BusinessRuleViolation):
        appt.mark_no_show(START - timedelta(minutes=1))
    with pytest.raises(BusinessRuleViolation):
        appt.start(START - timedelta(minutes=31))

    appt.start(START - timedelta(minutes=30))  # tolerância de 30 min
    assert appt.status == S.IN_PROGRESS


def test_cancel_requires_reason():
    with pytest.raises(BusinessRuleViolation):
        make().cancel(BEFORE, " ")


def test_allowed_transitions_consider_the_clock():
    appt = make()
    assert appt.allowed_transitions(BEFORE) == [S.CONFIRMED, S.CANCELLED]
    assert appt.allowed_transitions(AFTER) == [S.CONFIRMED, S.NO_SHOW]
    assert make(S.COMPLETED).allowed_transitions(AFTER) == []


def test_reschedule_returns_to_scheduled_and_keeps_history():
    appt = make(S.CONFIRMED)
    appt.reschedule(START + timedelta(days=2), BEFORE, duration_minutes=45)
    assert appt.status == S.SCHEDULED
    assert appt.end_time == START + timedelta(days=2, minutes=45)
    assert "Remarcada" in appt.history[-1].note

    with pytest.raises(BusinessRuleViolation):
        appt.reschedule(BEFORE - timedelta(hours=1), BEFORE)
    with pytest.raises(InvalidTransitionError):
        make(S.CANCELLED).reschedule(START + timedelta(days=2), BEFORE)


@pytest.mark.parametrize("duration", [5, 12, 245])
def test_invalid_durations(duration):
    with pytest.raises(BusinessRuleViolation):
        make(duration=duration)


def test_working_hours_rules():
    doctor = Professional(full_name="Dr. João (fictício)", professional_type=ProfessionalType.DOCTOR,
                          registry_number="CRM-PA 00001")
    doctor.set_working_hours([WorkingHours(1, time(8), time(12)), WorkingHours(1, time(14), time(18))])

    assert doctor.works_during(START, START + timedelta(minutes=30))
    assert not doctor.works_during(START.replace(hour=11, minute=45), START.replace(hour=12, minute=15))
    assert not doctor.works_during(START + timedelta(days=1), START + timedelta(days=1, minutes=30))

    with pytest.raises(BusinessRuleViolation):
        doctor.set_working_hours([WorkingHours(1, time(8), time(12)), WorkingHours(1, time(11), time(13))])
    with pytest.raises(BusinessRuleViolation):
        WorkingHours(7, time(8), time(9))
