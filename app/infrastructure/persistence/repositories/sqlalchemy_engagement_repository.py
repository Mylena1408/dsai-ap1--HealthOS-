import uuid

from sqlalchemy import case, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.engagement_repository import (
    AlertFilters, AuditFilters, AuditRepository, InboxQuery, InboxRepository, SystemAlertRepository,
)
from app.domain.entities.inbox import (
    Audience, InboxNotification, InboxStatus, NotificationCategory, Priority, Sector,
)
from app.domain.entities.system_alert import AlertCategory, AlertLevel, SystemAlert, SystemAlertStatus
from app.domain.events import DomainEvent, EventType
from app.infrastructure.persistence.models.engagement_model import (
    AuditEventModel, InboxNotificationModel, SystemAlertModel,
)


def _json_safe(value):
    """UUIDs e datas não são serializáveis em JSON; guardamos como texto."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class SQLAlchemyAuditRepository(AuditRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, event: DomainEvent) -> uuid.UUID:
        model = AuditEventModel(
            occurred_at=event.occurred_at, event_type=event.event_type.value, entity_type=event.entity_type,
            entity_id=event.entity_id, patient_id=event.patient_id, professional_id=event.professional_id,
            summary=event.summary[:500], data=_json_safe(event.data))
        self.session.add(model)
        await self.session.flush()
        return model.id

    async def search(self, filters: AuditFilters):
        conditions = []
        if filters.event_types:
            conditions.append(AuditEventModel.event_type.in_([t.value for t in filters.event_types]))
        for column, value in ((AuditEventModel.entity_type, filters.entity_type),
                              (AuditEventModel.entity_id, filters.entity_id),
                              (AuditEventModel.patient_id, filters.patient_id)):
            if value:
                conditions.append(column == value)
        if filters.date_from:
            conditions.append(AuditEventModel.occurred_at >= filters.date_from)
        if filters.date_to:
            conditions.append(AuditEventModel.occurred_at <= filters.date_to)
        total = await self.session.scalar(select(func.count()).select_from(AuditEventModel).where(*conditions))
        rows = await self.session.scalars(select(AuditEventModel).where(*conditions)
                                          .order_by(desc(AuditEventModel.occurred_at)).limit(filters.limit)
                                          .offset(filters.offset))
        return [(m.id, DomainEvent(
            event_type=EventType(m.event_type), occurred_at=m.occurred_at, entity_type=m.entity_type,
            entity_id=m.entity_id, summary=m.summary, patient_id=m.patient_id, professional_id=m.professional_id,
            data=m.data or {})) for m in rows], total

    async def count_by_type(self, date_from=None):
        stmt = select(AuditEventModel.event_type, func.count()).group_by(AuditEventModel.event_type)
        if date_from:
            stmt = stmt.where(AuditEventModel.occurred_at >= date_from)
        return dict((await self.session.execute(stmt)).all())


class SQLAlchemyInboxRepository(InboxRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, notification):
        model = await self.session.get(InboxNotificationModel, notification.id) if notification.id else None
        if model is None:
            model = InboxNotificationModel(id=notification.id or uuid.uuid4())
            self.session.add(model)
        for name in ("recipient_id", "title", "message", "link", "source_event", "created_at", "read_at", "archived_at"):
            setattr(model, name, getattr(notification, name))
        model.audience, model.category = notification.audience.value, notification.category.value
        model.sector = notification.sector.value if notification.sector else None
        model.priority, model.status = notification.priority.value, notification.status.value
        await self.session.flush()
        notification.id = model.id
        return notification

    async def get(self, notification_id):
        model = await self.session.get(InboxNotificationModel, notification_id)
        return self._to_domain(model) if model else None

    def _owner(self, query: InboxQuery):
        conditions = [InboxNotificationModel.audience == query.audience.value]
        if query.audience == Audience.SECTOR:
            conditions.append(InboxNotificationModel.sector == query.sector.value)
        else:
            conditions.append(InboxNotificationModel.recipient_id == query.recipient_id)
        return conditions

    async def search(self, query: InboxQuery):
        conditions = self._owner(query)
        if query.statuses:
            conditions.append(InboxNotificationModel.status.in_([s.value for s in query.statuses]))
        if query.category:
            conditions.append(InboxNotificationModel.category == query.category.value)
        total = await self.session.scalar(select(func.count()).select_from(InboxNotificationModel).where(*conditions))
        rows = await self.session.scalars(select(InboxNotificationModel).where(*conditions)
                                          .order_by(desc(InboxNotificationModel.created_at))
                                          .limit(query.limit).offset(query.offset))
        return [self._to_domain(m) for m in rows], total

    async def counts(self, query: InboxQuery):
        rows = await self.session.execute(select(InboxNotificationModel.status, func.count())
                                          .where(*self._owner(query)).group_by(InboxNotificationModel.status))
        return {InboxStatus(status): total for status, total in rows.all()}

    async def mark_all_read(self, query: InboxQuery, now):
        result = await self.session.execute(
            update(InboxNotificationModel)
            .where(*self._owner(query), InboxNotificationModel.status == InboxStatus.UNREAD.value)
            .values(status=InboxStatus.READ.value, read_at=now))
        return result.rowcount

    @staticmethod
    def _to_domain(m: InboxNotificationModel) -> InboxNotification:
        return InboxNotification(
            id=m.id, audience=Audience(m.audience), recipient_id=m.recipient_id,
            sector=Sector(m.sector) if m.sector else None, category=NotificationCategory(m.category),
            priority=Priority(m.priority), title=m.title, message=m.message, link=m.link,
            source_event=m.source_event, status=InboxStatus(m.status), created_at=m.created_at,
            read_at=m.read_at, archived_at=m.archived_at)


class SQLAlchemySystemAlertRepository(SystemAlertRepository):
    _FIELDS = ("rule_code", "dedup_key", "title", "message", "subject_type", "subject_id", "patient_id", "link",
               "first_detected_at", "last_detected_at", "acknowledged_at", "acknowledged_by", "resolved_at",
               "resolution_note", "auto_resolved")

    def __init__(self, session: AsyncSession):
        self.session = session

    async def open_alerts(self):
        rows = await self.session.scalars(select(SystemAlertModel)
                                          .where(SystemAlertModel.status != SystemAlertStatus.RESOLVED.value))
        return [self._to_domain(m) for m in rows]

    async def save(self, alert):
        model = await self.session.get(SystemAlertModel, alert.id) if alert.id else None
        if model is None:
            model = SystemAlertModel(id=alert.id or uuid.uuid4())
            self.session.add(model)
        for name in self._FIELDS:
            setattr(model, name, getattr(alert, name))
        model.category, model.level, model.status = alert.category.value, alert.level.value, alert.status.value
        await self.session.flush()
        alert.id = model.id
        return alert

    async def get(self, alert_id):
        model = await self.session.get(SystemAlertModel, alert_id)
        return self._to_domain(model) if model else None

    async def search(self, filters: AlertFilters):
        conditions = []
        for column, values in ((SystemAlertModel.status, filters.statuses),
                               (SystemAlertModel.category, filters.categories),
                               (SystemAlertModel.level, filters.levels)):
            if values:
                conditions.append(column.in_([v.value for v in values]))
        if filters.patient_id:
            conditions.append(SystemAlertModel.patient_id == filters.patient_id)
        if filters.rule_code:
            conditions.append(SystemAlertModel.rule_code == filters.rule_code)
        total = await self.session.scalar(select(func.count()).select_from(SystemAlertModel).where(*conditions))
        # Críticos primeiro, depois atenção e informativos; dentro do nível, os mais recentes.
        severity = case((SystemAlertModel.level == AlertLevel.CRITICAL.value, 0),
                        (SystemAlertModel.level == AlertLevel.WARNING.value, 1), else_=2)
        rows = await self.session.scalars(select(SystemAlertModel).where(*conditions)
                                          .order_by(severity, desc(SystemAlertModel.last_detected_at))
                                          .limit(filters.limit).offset(filters.offset))
        return [self._to_domain(m) for m in rows], total

    async def summary(self):
        rows = (await self.session.execute(
            select(SystemAlertModel.category, SystemAlertModel.level, func.count())
            .where(SystemAlertModel.status != SystemAlertStatus.RESOLVED.value)
            .group_by(SystemAlertModel.category, SystemAlertModel.level))).all()
        by_category, by_level = {}, {}
        for category, level, total in rows:
            by_category[category] = by_category.get(category, 0) + total
            by_level[level] = by_level.get(level, 0) + total
        return {"by_category": by_category, "by_level": by_level}

    def _to_domain(self, m: SystemAlertModel) -> SystemAlert:
        return SystemAlert(category=AlertCategory(m.category), level=AlertLevel(m.level),
                           status=SystemAlertStatus(m.status), id=m.id,
                           **{name: getattr(m, name) for name in self._FIELDS})
