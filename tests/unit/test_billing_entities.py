from datetime import datetime, timedelta
from decimal import Decimal
import uuid

import pytest

from app.domain.entities.billing import (
    BillingItem, BillingStatus, BillingType, Invoice, Payment, PaymentMethod,
)
from app.domain.exceptions.common import BusinessRuleViolation, ConflictError, InvalidTransitionError

NOW = datetime(2026, 10, 6, 10, 0)


def invoice_with(*prices: str) -> Invoice:
    invoice = Invoice(patient_id=uuid.uuid4(), invoice_number="FAT-T")
    for price in prices:
        invoice.add_item(BillingItem(description="Serviço", billing_type=BillingType.EXAM, unit_price=Decimal(price)))
    return invoice


def pay(amount: str, method=PaymentMethod.PIX) -> Payment:
    return Payment(amount=Decimal(amount), method=method, paid_at=NOW)


def test_issue_requires_draft_with_positive_total():
    with pytest.raises(BusinessRuleViolation):
        invoice_with().issue(NOW)
    with pytest.raises(BusinessRuleViolation, match="maior que zero"):
        invoice_with("0").issue(NOW)

    invoice = invoice_with("100", "50")
    invoice.issue(NOW)
    assert invoice.status == BillingStatus.PENDING and invoice.due_date == NOW + timedelta(days=15)
    with pytest.raises(InvalidTransitionError):
        invoice.issue(NOW)
    with pytest.raises(ValueError):  # regra original: itens só em rascunho
        invoice.add_item(BillingItem(unit_price=Decimal(1)))


def test_partial_then_full_payment():
    invoice = invoice_with("100", "50.50")
    with pytest.raises(ConflictError):  # rascunho não recebe pagamento
        invoice.register_payment(pay("10"))
    invoice.issue(NOW)

    invoice.register_payment(pay("100", PaymentMethod.INSURANCE))
    assert invoice.status == BillingStatus.PARTIALLY_PAID and invoice.balance() == Decimal("50.50")
    with pytest.raises(BusinessRuleViolation, match="excede"):
        invoice.register_payment(pay("50.51"))
    with pytest.raises(BusinessRuleViolation):
        invoice.register_payment(pay("0"))

    invoice.register_payment(pay("50.50"))
    assert invoice.status == BillingStatus.PAID and invoice.balance() == 0
    with pytest.raises(ConflictError):
        invoice.register_payment(pay("1"))


def test_overdue_is_derived_from_due_date():
    invoice = invoice_with("80")
    invoice.issue(NOW)
    assert invoice.effective_status(NOW + timedelta(days=15)) == BillingStatus.PENDING
    assert invoice.effective_status(NOW + timedelta(days=16)) == BillingStatus.OVERDUE
    invoice.register_payment(pay("30"))
    assert invoice.effective_status(NOW + timedelta(days=16)) == BillingStatus.OVERDUE
    invoice.register_payment(pay("50"))
    assert invoice.effective_status(NOW + timedelta(days=16)) == BillingStatus.PAID


def test_cancel_rules():
    paid = invoice_with("10")
    paid.issue(NOW)
    paid.register_payment(pay("5"))
    with pytest.raises(BusinessRuleViolation, match="pagamentos"):
        paid.cancel("Erro de lançamento", NOW)

    invoice = invoice_with("10")
    with pytest.raises(BusinessRuleViolation, match="motivo"):
        invoice.cancel("  ", NOW)
    invoice.cancel("  Erro de lançamento ", NOW)
    assert invoice.status == BillingStatus.CANCELLED and invoice.cancellation_reason == "Erro de lançamento"
    with pytest.raises(InvalidTransitionError):
        invoice.cancel("de novo", NOW)
