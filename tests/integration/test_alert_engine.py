from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.application.interfaces.engagement_repository import AlertFilters, AuditFilters, InboxQuery
from app.application.use_cases.alert_engine_use_case import AlertEngineUseCase
from app.domain.entities.inbox import Audience, Sector
from app.domain.entities.system_alert import AlertLevel, SystemAlertStatus
from app.domain.events import EventType
from app.domain.exceptions.common import BusinessRuleViolation
from app.infrastructure.events import build_publisher
from app.infrastructure.persistence.models.medication_model import InventoryItemModel
from app.infrastructure.persistence.models.pharmacy_model import StockLotModel
from app.infrastructure.persistence.repositories.sqlalchemy_alert_detector import SQLAlchemyAlertDetector
from app.infrastructure.persistence.repositories.sqlalchemy_engagement_repository import (
    SQLAlchemyAuditRepository, SQLAlchemyInboxRepository, SQLAlchemySystemAlertRepository,
)
from app.infrastructure.seed.demo_seed import seed_demo_data

NOW = datetime(2026, 10, 6, 12, 0)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
async def ctx(db_session):
    await seed_demo_data(db_session, patients=15, appointments=40, exams=40, prescriptions=10, now=NOW)
    clock = Clock(NOW)
    engine = AlertEngineUseCase(SQLAlchemySystemAlertRepository(db_session), SQLAlchemyAlertDetector(db_session),
                                build_publisher(db_session), clock=clock)
    return dict(session=db_session, clock=clock, engine=engine)


async def open_alerts(engine, **filters):
    return (await engine.search(AlertFilters(statuses=[SystemAlertStatus.ACTIVE, SystemAlertStatus.ACKNOWLEDGED],
                                             limit=500, **filters))).items


async def test_seed_evaluation_opens_alerts_once_and_notifies_sectors(ctx):
    # O seed já executa a primeira avaliação; uma nova execução não duplica alertas.
    opened = await open_alerts(ctx["engine"])
    report = await ctx["engine"].evaluate()
    assert opened and report.opened == 0 and report.refreshed == len(opened) == sum(report.by_rule.values())
    assert report.by_rule["ESTOQUE_BAIXO"] > 0  # o seed deixa estoques críticos de propósito
    assert report.by_rule["LOTE_VENCENDO"] > 0

    pharmacy_inbox = await SQLAlchemyInboxRepository(ctx["session"]).search(
        InboxQuery(audience=Audience.SECTOR, sector=Sector.PHARMACY, limit=500))
    assert pharmacy_inbox[1] >= report.by_rule["ESTOQUE_BAIXO"] + report.by_rule["LOTE_VENCENDO"]
    _, raised = await SQLAlchemyAuditRepository(ctx["session"]).search(
        AuditFilters(event_types=[EventType.ALERT_RAISED], limit=1))
    assert raised == len(opened)


async def test_alert_is_auto_resolved_when_condition_disappears(ctx):
    await ctx["engine"].evaluate(["ESTOQUE_BAIXO"])
    alert = (await open_alerts(ctx["engine"], rule_code="ESTOQUE_BAIXO"))[0]
    medication_id, location = alert.dedup_key.split(":")[1:]
    item = (await ctx["session"].scalars(select(InventoryItemModel).where(
        InventoryItemModel.location_id == location))).all()
    item = next(i for i in item if str(i.medication_id) == medication_id)
    item.quantity = item.min_threshold + 100  # reposição: condição deixa de existir
    await ctx["session"].flush()

    report = await ctx["engine"].evaluate(["ESTOQUE_BAIXO"])
    assert report.auto_resolved == 1
    resolved = await ctx["engine"].search(AlertFilters(statuses=[SystemAlertStatus.RESOLVED]))
    assert resolved.items[0].id == alert.id and resolved.items[0].auto_resolved


async def test_lot_alert_escalates_when_the_lot_expires(ctx):
    lot = (await ctx["session"].scalars(select(StockLotModel).where(
        StockLotModel.quantity > 0, StockLotModel.expiration_date > NOW.date()))).first()
    lot.expiration_date = NOW.date() + timedelta(days=3)
    await ctx["session"].flush()
    await ctx["engine"].evaluate(["LOTE_VENCENDO"])
    alert = next(a for a in await open_alerts(ctx["engine"], rule_code="LOTE_VENCENDO") if a.subject_id == lot.id)
    assert alert.level == AlertLevel.WARNING

    ctx["clock"].now = NOW + timedelta(days=5)
    report = await ctx["engine"].evaluate(["LOTE_VENCENDO"])
    assert report.escalated >= 1
    alert = next(a for a in await open_alerts(ctx["engine"], rule_code="LOTE_VENCENDO") if a.subject_id == lot.id)
    assert alert.level == AlertLevel.CRITICAL and "venceu" in alert.message


async def test_manual_acknowledge_and_resolve(ctx):
    await ctx["engine"].evaluate(["EXAME_FORA_REFERENCIA"])
    alert = (await open_alerts(ctx["engine"]))[0]
    acknowledged = await ctx["engine"].acknowledge(alert.id, "Coordenação (demo)")
    assert acknowledged.status == SystemAlertStatus.ACKNOWLEDGED
    resolved = await ctx["engine"].resolve(alert.id, "Paciente orientado e retorno agendado")
    assert resolved.status == SystemAlertStatus.RESOLVED and not resolved.auto_resolved
    summary = await ctx["engine"].summary()
    assert sum(summary["by_level"].values()) == len(await open_alerts(ctx["engine"]))


async def test_unknown_rule_is_rejected(db_session):
    engine = AlertEngineUseCase(SQLAlchemySystemAlertRepository(db_session), SQLAlchemyAlertDetector(db_session))
    with pytest.raises(BusinessRuleViolation):
        await engine.evaluate(["REGRA_INEXISTENTE"])
