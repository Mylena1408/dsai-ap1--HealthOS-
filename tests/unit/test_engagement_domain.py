from datetime import datetime, timedelta
import uuid

import pytest

from app.application.services.event_handlers import NotificationPolicy
from app.application.services.events import InProcessPublisher
from app.domain.entities.inbox import Audience, InboxNotification, InboxStatus, NotificationCategory, Priority, Sector
from app.domain.entities.system_alert import (
    AlertCandidate, AlertCategory, AlertLevel, SystemAlert, SystemAlertStatus,
)
from app.domain.events import DomainEvent, EventType
from app.domain.exceptions.common import BusinessRuleViolation, InvalidTransitionError

NOW = datetime(2026, 10, 6, 10, 0)


def notification(**overrides) -> InboxNotification:
    data = dict(audience=Audience.SECTOR, sector=Sector.PHARMACY, category=NotificationCategory.MEDICATION,
                title="Teste", message="Mensagem", created_at=NOW)
    data.update(overrides)
    return InboxNotification(**data)


def test_inbox_lifecycle():
    item = notification()
    item.mark_read(NOW)
    with pytest.raises(InvalidTransitionError):
        item.mark_read(NOW)
    item.mark_unread()
    item.archive(NOW + timedelta(minutes=1))
    assert item.status == InboxStatus.ARCHIVED and item.read_at is not None  # arquivar implica ter visto
    item.unarchive()
    assert item.status == InboxStatus.READ
    with pytest.raises(InvalidTransitionError):
        item.unarchive()


def test_inbox_requires_a_destination():
    with pytest.raises(BusinessRuleViolation, match="setor"):
        notification(sector=None)
    with pytest.raises(BusinessRuleViolation, match="destinatário"):
        notification(audience=Audience.PATIENT, sector=None)


def candidate(level=AlertLevel.WARNING) -> AlertCandidate:
    return AlertCandidate(rule_code="ESTOQUE_BAIXO", dedup_key="ESTOQUE_BAIXO:x", category=AlertCategory.STOCK,
                          level=level, title="Estoque baixo", message="m", subject_type="Medicamento")


def test_alert_lifecycle_and_escalation():
    alert = SystemAlert.open(candidate(), NOW)
    assert alert.status == SystemAlertStatus.ACTIVE and alert.is_open
    assert alert.refresh(candidate(AlertLevel.CRITICAL), NOW + timedelta(hours=1)) is True  # agravou
    assert alert.refresh(candidate(AlertLevel.WARNING), NOW + timedelta(hours=2)) is False
    with pytest.raises(BusinessRuleViolation):
        alert.acknowledge("x", NOW)
    alert.acknowledge("Ana (farmácia)", NOW)
    with pytest.raises(BusinessRuleViolation):
        alert.resolve(NOW, note="ok")  # nota curta demais para resolução manual
    alert.resolve(NOW, note="Pedido de compra emitido")
    assert not alert.is_open and not alert.auto_resolved
    with pytest.raises(InvalidTransitionError):
        alert.resolve(NOW, automatic=True)


def test_automatic_resolution_has_default_note():
    alert = SystemAlert.open(candidate(), NOW)
    alert.resolve(NOW, automatic=True)
    assert alert.auto_resolved and "automaticamente" in alert.resolution_note


class FakeInbox:
    def __init__(self):
        self.saved = []

    async def save(self, item):
        self.saved.append(item)
        return item


async def test_notification_policy_routes_events():
    inbox = FakeInbox()
    publisher = InProcessPublisher([NotificationPolicy(inbox)])
    patient, doctor = uuid.uuid4(), uuid.uuid4()

    await publisher.publish(DomainEvent(EventType.EXAM_RELEASED, NOW, "Exame", uuid.uuid4(), "Resultado liberado",
                                        patient_id=patient, professional_id=doctor, data={"abnormal": True}))
    await publisher.publish(DomainEvent(EventType.ALERT_RAISED, NOW, "Alerta", uuid.uuid4(), "Alerta gerado",
                                        data={"sector": "LABORATORIO", "level": "CRITICO", "title": "Exame atrasado"}))
    await publisher.publish(DomainEvent(EventType.ALLERGY_RECORDED, NOW, "Alergia", uuid.uuid4(), "Sem notificação"))

    summary = [(n.audience, n.recipient_id or n.sector, n.priority) for n in inbox.saved]
    assert summary == [(Audience.PATIENT, patient, Priority.NORMAL), (Audience.PROFESSIONAL, doctor, Priority.HIGH),
                       (Audience.SECTOR, Sector.LABORATORY, Priority.HIGH)]
    assert inbox.saved[-1].title == "Novo alerta: Exame atrasado"
    assert len(publisher.published) == 3  # todos os eventos passam pelo publicador


async def test_events_without_professional_skip_personal_notification():
    inbox = FakeInbox()
    await NotificationPolicy(inbox)(DomainEvent(EventType.EXAM_RELEASED, NOW, "Exame", uuid.uuid4(), "x",
                                                patient_id=uuid.uuid4(), professional_id=None))
    assert [n.audience for n in inbox.saved] == [Audience.PATIENT]


async def test_prescription_notifies_pharmacy_nursing_and_patient():
    inbox = FakeInbox()
    patient = uuid.uuid4()
    await NotificationPolicy(inbox)(DomainEvent(EventType.PRESCRIPTION_ISSUED, NOW, "Prescricao", uuid.uuid4(),
                                                "Prescrição emitida", patient_id=patient))
    assert [(n.audience, n.recipient_id or n.sector) for n in inbox.saved] == [
        (Audience.SECTOR, Sector.PHARMACY), (Audience.SECTOR, Sector.NURSING), (Audience.PATIENT, patient)]
    nursing = inbox.saved[1]
    assert nursing.title == "Nova prescrição para acompanhamento"
    assert nursing.link == f"/app/prontuario?patient={patient}"
