from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional
import uuid

from app.application.dtos.common import Page
from app.application.interfaces.engagement_repository import AlertDetector, AlertFilters, SystemAlertRepository
from app.application.services.alert_rules import RULES, RULES_BY_CODE
from app.application.services.events import EventPublisher, NullPublisher
from app.domain.entities.system_alert import SystemAlert
from app.domain.events import DomainEvent, EventType
from app.domain.exceptions.common import BusinessRuleViolation, EntityNotFoundError


@dataclass
class EvaluationReport:
    evaluated_at: datetime
    opened: int = 0
    refreshed: int = 0
    escalated: int = 0
    auto_resolved: int = 0
    by_rule: dict[str, int] = field(default_factory=dict)  # condições detectadas por regra


class AlertEngineUseCase:
    """
    Avalia as regras, abre alertas para condições novas, atualiza os já abertos e resolve
    automaticamente os que deixaram de ser detectados. Cada abertura/agravamento publica
    ALERTA_GERADO (que vira notificação para o setor responsável).
    """

    def __init__(self, repo: SystemAlertRepository, detector: AlertDetector,
                 events: EventPublisher = NullPublisher(), clock: Callable[[], datetime] = datetime.now):
        self.repo = repo
        self.detector = detector
        self.events = events
        self.clock = clock

    async def evaluate(self, rule_codes: Optional[list[str]] = None) -> EvaluationReport:
        now = self.clock().replace(microsecond=0)
        unknown = set(rule_codes or []) - RULES_BY_CODE.keys()
        if unknown:
            raise BusinessRuleViolation(f"Regras desconhecidas: {', '.join(sorted(unknown))}.")
        rules = [r for r in RULES if not rule_codes or r.code in rule_codes]
        report = EvaluationReport(evaluated_at=now)
        open_alerts = {a.dedup_key: a for a in await self.repo.open_alerts()}

        for rule in rules:
            candidates = await self.detector.detect(rule.code, now)
            report.by_rule[rule.code] = len(candidates)
            detected = set()
            for candidate in candidates:
                detected.add(candidate.dedup_key)
                alert = open_alerts.get(candidate.dedup_key)
                if alert is None:
                    alert = await self.repo.save(SystemAlert.open(candidate, now))
                    report.opened += 1
                    await self._publish(EventType.ALERT_RAISED, alert, now, rule.sector.value)
                elif alert.refresh(candidate, now):
                    await self.repo.save(alert)
                    report.escalated += 1
                    await self._publish(EventType.ALERT_RAISED, alert, now, rule.sector.value, escalated=True)
                else:
                    await self.repo.save(alert)
                    report.refreshed += 1
            # Condições que sumiram nesta execução resolvem o alerta automaticamente.
            for alert in open_alerts.values():
                if alert.rule_code == rule.code and alert.dedup_key not in detected:
                    alert.resolve(now, automatic=True)
                    await self.repo.save(alert)
                    report.auto_resolved += 1
                    await self._publish(EventType.ALERT_RESOLVED, alert, now, rule.sector.value)
        return report

    # ------------------------------------------------------------ operação manual

    async def search(self, filters: AlertFilters) -> Page[SystemAlert]:
        items, total = await self.repo.search(filters)
        return Page(items=items, total=total, limit=filters.limit, offset=filters.offset)

    async def acknowledge(self, alert_id: uuid.UUID, by: str) -> SystemAlert:
        alert = await self._get(alert_id)
        alert.acknowledge(by, self.clock())
        return await self.repo.save(alert)

    async def resolve(self, alert_id: uuid.UUID, note: str) -> SystemAlert:
        alert = await self._get(alert_id)
        now = self.clock()
        alert.resolve(now, note)
        saved = await self.repo.save(alert)
        await self._publish(EventType.ALERT_RESOLVED, saved, now, RULES_BY_CODE[alert.rule_code].sector.value)
        return saved

    async def summary(self) -> dict[str, dict[str, int]]:
        return await self.repo.summary()

    async def _get(self, alert_id: uuid.UUID) -> SystemAlert:
        alert = await self.repo.get(alert_id)
        if not alert:
            raise EntityNotFoundError("Alerta", alert_id)
        return alert

    async def _publish(self, event_type: EventType, alert: SystemAlert, now: datetime, sector: str,
                       escalated: bool = False) -> None:
        verb = "resolvido" if event_type == EventType.ALERT_RESOLVED else "gerado"
        await self.events.publish(DomainEvent(
            event_type=event_type, occurred_at=now, entity_type="Alerta", entity_id=alert.id,
            patient_id=alert.patient_id, summary=f"Alerta {verb}: {alert.title} — {alert.message}",
            data={"rule": alert.rule_code, "level": alert.level.value, "title": alert.title, "sector": sector,
                  "escalated": escalated},
        ))
