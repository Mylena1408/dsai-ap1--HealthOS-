from datetime import datetime
from typing import Callable
import uuid

from app.application.dtos.common import Page
from app.application.dtos.engagement_dto import AuditEventDTO, InboxCountsDTO, InboxNotificationDTO
from app.application.interfaces.engagement_repository import AuditFilters, AuditRepository, InboxQuery, InboxRepository
from app.domain.entities.inbox import Audience, InboxNotification, InboxStatus
from app.domain.exceptions.common import BusinessRuleViolation, EntityNotFoundError


def _dto(n: InboxNotification) -> InboxNotificationDTO:
    return InboxNotificationDTO(**{name: getattr(n, name) for name in InboxNotificationDTO.model_fields})


class InboxUseCase:
    """Caixa de entrada por perfil de demonstração: paciente, profissional ou setor."""

    def __init__(self, repo: InboxRepository, clock: Callable[[], datetime] = datetime.now):
        self.repo = repo
        self.clock = clock

    async def page(self, query: InboxQuery) -> Page[InboxNotificationDTO]:
        self._validate(query)
        items, total = await self.repo.search(query)
        return Page(items=[_dto(n) for n in items], total=total, limit=query.limit, offset=query.offset)

    async def counts(self, query: InboxQuery) -> InboxCountsDTO:
        self._validate(query)
        counts = await self.repo.counts(query)
        return InboxCountsDTO(unread=counts.get(InboxStatus.UNREAD, 0), read=counts.get(InboxStatus.READ, 0),
                              archived=counts.get(InboxStatus.ARCHIVED, 0))

    async def change(self, notification_id: uuid.UUID, action: str) -> InboxNotificationDTO:
        notification = await self.repo.get(notification_id)
        if not notification:
            raise EntityNotFoundError("Notificação", notification_id)
        now = self.clock()
        if action == "read":
            notification.mark_read(now)
        elif action == "unread":
            notification.mark_unread()
        elif action == "archive":
            notification.archive(now)
        else:
            notification.unarchive()
        return _dto(await self.repo.save(notification))

    async def mark_all_read(self, query: InboxQuery) -> int:
        self._validate(query)
        return await self.repo.mark_all_read(query, self.clock())

    @staticmethod
    def _validate(query: InboxQuery) -> None:
        if query.audience == Audience.SECTOR and query.sector is None:
            raise BusinessRuleViolation("Informe o setor da caixa de entrada.")
        if query.audience != Audience.SECTOR and query.recipient_id is None:
            raise BusinessRuleViolation("Informe o paciente ou profissional da caixa de entrada.")


class AuditUseCase:
    """Consulta da trilha de auditoria (somente leitura)."""

    def __init__(self, repo: AuditRepository):
        self.repo = repo

    async def search(self, filters: AuditFilters) -> Page[AuditEventDTO]:
        rows, total = await self.repo.search(filters)
        return Page(items=[AuditEventDTO(id=event_id, occurred_at=e.occurred_at, event_type=e.event_type,
                                         entity_type=e.entity_type, entity_id=e.entity_id, patient_id=e.patient_id,
                                         professional_id=e.professional_id, summary=e.summary, data=e.data)
                           for event_id, e in rows], total=total, limit=filters.limit, offset=filters.offset)

    async def counts(self, date_from: datetime | None = None) -> dict[str, int]:
        return await self.repo.count_by_type(date_from)
