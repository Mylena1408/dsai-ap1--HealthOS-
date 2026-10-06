from datetime import date, datetime, timedelta
import uuid

import pytest

from app.domain.entities.pharmacy import (
    ItemStatus, Prescription, PrescriptionItem, PrescriptionStatus as PS, StockLot, allocate_fefo,
)
from app.domain.exceptions.common import BusinessRuleViolation, ConflictError, InvalidTransitionError

TODAY = date(2026, 10, 6)
NOW = datetime(2026, 10, 6, 10, 0)
MED = uuid.uuid4()


def lot(number, expires_in_days, quantity, received_days_ago=10):
    return StockLot(medication_id=MED, location="FARMACIA_CENTRAL", lot_number=number,
                    expiration_date=TODAY + timedelta(days=expires_in_days), quantity=quantity,
                    received_at=NOW - timedelta(days=received_days_ago), id=uuid.uuid4())


def test_fefo_uses_earliest_expiration_first_then_unlotted_stock():
    late, early, expired = lot("late", 300, 10), lot("early", 20, 5), lot("old", -1, 50)
    plan = allocate_fefo([late, early, expired], unlotted=4, requested=17, today=TODAY)
    assert [(p[0].lot_number if p[0] else None, p[1]) for p in plan] == [("EARLY", 5), ("LATE", 10), (None, 2)]


def test_fefo_never_uses_expired_lots():
    with pytest.raises(ConflictError, match="disponível 3"):
        allocate_fefo([lot("old", -1, 100), lot("ok", 10, 3)], unlotted=0, requested=4, today=TODAY)
    with pytest.raises(BusinessRuleViolation):
        allocate_fefo([], unlotted=10, requested=0, today=TODAY)


def test_lot_number_is_normalized_and_take_checks_balance():
    item = lot(" ab-12 ", 30, 5)
    assert item.lot_number == "AB-12"
    with pytest.raises(BusinessRuleViolation):
        item.take(6)
    item.take(5)
    assert item.quantity == 0


def make_prescription(*quantities) -> Prescription:
    items = [PrescriptionItem(medication_id=uuid.uuid4(), dose="1 comprimido", frequency="8/8h",
                              duration_days=7, quantity=q, id=uuid.uuid4()) for q in quantities]
    return Prescription(patient_id=uuid.uuid4(), prescriber_id=uuid.uuid4(), issued_at=NOW, items=items)


def test_prescription_status_follows_dispensed_quantities():
    prescription = make_prescription(20, 10)
    first, second = prescription.items
    first.register_dispensed(20)
    prescription.refresh_status()
    assert prescription.status == PS.PARTIALLY_DISPENSED

    with pytest.raises(BusinessRuleViolation, match="restam 10"):
        second.register_dispensed(11)
    second.register_dispensed(10)
    prescription.refresh_status()
    assert prescription.status == PS.DISPENSED
    with pytest.raises(InvalidTransitionError):
        prescription.ensure_dispensable(NOW)
    with pytest.raises(InvalidTransitionError):
        prescription.cancel("Tarde demais")


def test_suspended_items_do_not_block_completion_and_cannot_be_dispensed():
    prescription = make_prescription(5, 5)
    first, second = prescription.items
    second.suspend("Reação adversa fictícia")
    with pytest.raises(BusinessRuleViolation, match="em uso"):
        second.register_dispensed(1)
    first.register_dispensed(5)
    prescription.refresh_status()
    assert prescription.status == PS.DISPENSED  # o item suspenso não tem saldo exigível

    second.resume()
    assert second.status == ItemStatus.IN_USE
    with pytest.raises(InvalidTransitionError):
        second.resume()


def test_prescription_expiration_and_validation():
    prescription = make_prescription(5)
    prescription.ensure_dispensable(NOW + timedelta(days=30))
    with pytest.raises(BusinessRuleViolation, match="vencida"):
        prescription.ensure_dispensable(NOW + timedelta(days=31))

    medication = uuid.uuid4()
    with pytest.raises(BusinessRuleViolation, match="duas vezes"):
        Prescription(patient_id=uuid.uuid4(), prescriber_id=uuid.uuid4(), issued_at=NOW, items=[
            PrescriptionItem(medication_id=medication, dose="1", frequency="1x", duration_days=1, quantity=1),
            PrescriptionItem(medication_id=medication, dose="1", frequency="1x", duration_days=1, quantity=1)])
    with pytest.raises(BusinessRuleViolation):
        Prescription(patient_id=uuid.uuid4(), prescriber_id=uuid.uuid4(), issued_at=NOW, items=[])
    with pytest.raises(BusinessRuleViolation):
        PrescriptionItem(medication_id=medication, dose="1", frequency="1x", duration_days=0, quantity=1)


def test_cancel_requires_reason_and_keeps_history_of_partial_dispensation():
    prescription = make_prescription(10)
    prescription.items[0].register_dispensed(4)
    prescription.refresh_status()
    with pytest.raises(BusinessRuleViolation):
        prescription.cancel("")
    prescription.cancel("Troca de tratamento")
    prescription.refresh_status()  # cancelada não volta a outro status
    assert prescription.status == PS.CANCELLED and prescription.items[0].dispensed_quantity == 4
