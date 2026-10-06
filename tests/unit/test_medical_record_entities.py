from datetime import date, datetime
import uuid

import pytest

from app.domain.entities.medical_record import (
    Allergy, AllergyCategory, AllergySeverity, AllergyStatus, Condition, ConditionStatus as CS, Diagnosis,
    DiagnosisCertainty, EmergencyContact, PatientProfile, Procedure,
)
from app.domain.exceptions.common import BusinessRuleViolation, InvalidTransitionError

TODAY = date(2026, 10, 6)
PID = uuid.uuid4()


def contact(name="Contato Fictício", primary=False):
    return EmergencyContact(full_name=name, relationship="Irmã", phone="(91) 98888-7777",
                            is_primary=primary, id=uuid.uuid4())


def test_emergency_contacts_keep_exactly_one_primary_and_a_limit():
    profile = PatientProfile(patient_id=PID)
    first, second, third = contact("Ana Exemplo"), contact("Bruno Exemplo"), contact("Carla Exemplo", primary=True)
    profile.add_contact(first)
    profile.add_contact(second)
    assert first.is_primary and not second.is_primary  # o primeiro vira principal

    profile.add_contact(third)
    assert [c.is_primary for c in profile.emergency_contacts] == [False, False, True]
    with pytest.raises(BusinessRuleViolation):
        profile.add_contact(contact("Quarto Contato"))

    profile.remove_contact(third.id)
    assert sum(c.is_primary for c in profile.emergency_contacts) == 1
    with pytest.raises(BusinessRuleViolation):
        profile.remove_contact(uuid.uuid4())


def test_emergency_contact_validates_phone():
    with pytest.raises(BusinessRuleViolation):
        EmergencyContact(full_name="Fulano Exemplo", relationship="Pai", phone="123")


def test_allergy_resolution_happens_once():
    allergy = Allergy(patient_id=PID, substance=" Penicilina ", category=AllergyCategory.MEDICATION,
                      severity=AllergySeverity.SEVERE)
    assert allergy.substance == "Penicilina"
    assert allergy.same_substance("penicilina")
    allergy.resolve(datetime(2026, 10, 6))
    assert allergy.status == AllergyStatus.RESOLVED
    with pytest.raises(InvalidTransitionError):
        allergy.resolve(datetime(2026, 10, 7))


@pytest.mark.parametrize("path", [
    [CS.CONTROLLED, CS.ACTIVE, CS.RESOLVED],
    [CS.RESOLVED, CS.ACTIVE],  # recidiva
])
def test_condition_valid_paths(path):
    condition = Condition(patient_id=PID, name="Condição fictícia", onset_date=date(2020, 1, 1))
    for target in path:
        condition.change_status(target, TODAY)
    assert condition.status == path[-1]
    assert (condition.resolved_date is not None) == (path[-1] == CS.RESOLVED)


def test_condition_invalid_transition_and_dates():
    condition = Condition(patient_id=PID, name="Condição fictícia", status=CS.RESOLVED)
    with pytest.raises(InvalidTransitionError):
        condition.change_status(CS.CONTROLLED, TODAY)
    with pytest.raises(BusinessRuleViolation):
        Condition(patient_id=PID, name="Datas trocadas", onset_date=date(2025, 1, 2), resolved_date=date(2025, 1, 1))
    with pytest.raises(BusinessRuleViolation):
        Condition(patient_id=PID, name="Futuro", onset_date=date(2030, 1, 1)).validate_dates(TODAY)


def test_diagnosis_certainty_only_moves_from_suspected():
    diagnosis = Diagnosis(patient_id=PID, description="Hipótese fictícia")
    diagnosis.confirm()
    assert diagnosis.certainty == DiagnosisCertainty.CONFIRMED
    with pytest.raises(InvalidTransitionError):
        diagnosis.rule_out()


def test_procedure_cannot_be_in_the_future():
    procedure = Procedure(patient_id=PID, name="Curativo simples", performed_at=datetime(2026, 10, 7))
    with pytest.raises(BusinessRuleViolation):
        procedure.validate_date(datetime(2026, 10, 6))
