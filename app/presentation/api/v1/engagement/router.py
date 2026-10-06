"""Alertas por regra, caixa de notificações e trilha de auditoria."""
from datetime import date, datetime, time
from typing import Literal, Optional
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.common import Page
from app.application.dtos.engagement_dto import (
    AcknowledgeDTO, AlertRuleDTO, AuditEventDTO, EvaluateDTO, EvaluationReportDTO, InboxCountsDTO,
    InboxNotificationDTO, ResolveDTO, SystemAlertDTO,
)
from app.application.interfaces.engagement_repository import AlertFilters, AuditFilters, InboxQuery
from app.application.services.alert_rules import RULES
from app.application.use_cases.alert_engine_use_case import AlertEngineUseCase
from app.application.use_cases.inbox_use_case import AuditUseCase, InboxUseCase
from app.domain.entities.inbox import Audience, InboxStatus, NotificationCategory, Sector
from app.domain.entities.system_alert import AlertCategory, AlertLevel, SystemAlert, SystemAlertStatus
from app.domain.events import EventType
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.sqlalchemy_alert_detector import SQLAlchemyAlertDetector
from app.infrastructure.persistence.repositories.sqlalchemy_engagement_repository import (
    SQLAlchemyAuditRepository, SQLAlchemyInboxRepository, SQLAlchemySystemAlertRepository,
)
from app.presentation.api.dependencies import get_events

router = APIRouter()


async def get_engine(session: AsyncSession = Depends(get_db), events=Depends(get_events)) -> AlertEngineUseCase:
    return AlertEngineUseCase(SQLAlchemySystemAlertRepository(session), SQLAlchemyAlertDetector(session), events)


async def get_inbox(session: AsyncSession = Depends(get_db)) -> InboxUseCase:
    return InboxUseCase(SQLAlchemyInboxRepository(session))


async def get_audit(session: AsyncSession = Depends(get_db)) -> AuditUseCase:
    return AuditUseCase(SQLAlchemyAuditRepository(session))


def _alert_dto(alert: SystemAlert) -> SystemAlertDTO:
    return SystemAlertDTO(**{name: getattr(alert, name) for name in SystemAlertDTO.model_fields})


def _inbox_query(audience: Audience, recipient_id: Optional[uuid.UUID], sector: Optional[Sector],
                 statuses: Optional[list[InboxStatus]] = None, category: Optional[NotificationCategory] = None,
                 limit: int = 20, offset: int = 0) -> InboxQuery:
    return InboxQuery(audience=audience, recipient_id=recipient_id, sector=sector, statuses=statuses or [],
                      category=category, limit=limit, offset=offset)


# ---------------------------------------------------------------------- alertas

@router.get("/alerts/rules", response_model=list[AlertRuleDTO], tags=["Alertas por Regra"])
async def list_rules():
    return [AlertRuleDTO(code=r.code, category=r.category, description=r.description, sector=r.sector) for r in RULES]


@router.post("/alerts/evaluate", response_model=EvaluationReportDTO, tags=["Alertas por Regra"],
             summary="Executa as regras agora (também roda periodicamente em segundo plano)")
async def evaluate_alerts(request: Optional[EvaluateDTO] = None, engine: AlertEngineUseCase = Depends(get_engine)):
    report = await engine.evaluate(request.rules if request else None)
    return EvaluationReportDTO(**vars(report))


@router.get("/alerts", response_model=Page[SystemAlertDTO], tags=["Alertas por Regra"])
async def search_alerts(
    status: Optional[list[SystemAlertStatus]] = Query(None), category: Optional[list[AlertCategory]] = Query(None),
    level: Optional[list[AlertLevel]] = Query(None), patient_id: Optional[uuid.UUID] = None,
    rule_code: Optional[str] = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    engine: AlertEngineUseCase = Depends(get_engine),
):
    page = await engine.search(AlertFilters(statuses=status or [], categories=category or [], levels=level or [],
                                            patient_id=patient_id, rule_code=rule_code, limit=limit, offset=offset))
    return Page(items=[_alert_dto(a) for a in page.items], total=page.total, limit=limit, offset=offset)


@router.get("/alerts/summary", tags=["Alertas por Regra"], summary="Alertas abertos por categoria e nível")
async def alerts_summary(engine: AlertEngineUseCase = Depends(get_engine)):
    return await engine.summary()


@router.post("/alerts/{alert_id}/acknowledge", response_model=SystemAlertDTO, tags=["Alertas por Regra"])
async def acknowledge_alert(alert_id: uuid.UUID, request: AcknowledgeDTO, engine: AlertEngineUseCase = Depends(get_engine)):
    return _alert_dto(await engine.acknowledge(alert_id, request.by))


@router.post("/alerts/{alert_id}/resolve", response_model=SystemAlertDTO, tags=["Alertas por Regra"])
async def resolve_alert(alert_id: uuid.UUID, request: ResolveDTO, engine: AlertEngineUseCase = Depends(get_engine)):
    return _alert_dto(await engine.resolve(alert_id, request.note))


# ---------------------------------------------------------------- notificações

@router.get("/inbox", response_model=Page[InboxNotificationDTO], tags=["Notificações Internas"])
async def list_inbox(audience: Audience, recipient_id: Optional[uuid.UUID] = None, sector: Optional[Sector] = None,
                     status: Optional[list[InboxStatus]] = Query(None), category: Optional[NotificationCategory] = None,
                     limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                     use_case: InboxUseCase = Depends(get_inbox)):
    return await use_case.page(_inbox_query(audience, recipient_id, sector, status, category, limit, offset))


@router.get("/inbox/counts", response_model=InboxCountsDTO, tags=["Notificações Internas"])
async def inbox_counts(audience: Audience, recipient_id: Optional[uuid.UUID] = None, sector: Optional[Sector] = None,
                       use_case: InboxUseCase = Depends(get_inbox)):
    return await use_case.counts(_inbox_query(audience, recipient_id, sector))


@router.post("/inbox/mark-all-read", tags=["Notificações Internas"])
async def mark_all_read(audience: Audience, recipient_id: Optional[uuid.UUID] = None, sector: Optional[Sector] = None,
                        use_case: InboxUseCase = Depends(get_inbox)):
    return {"updated": await use_case.mark_all_read(_inbox_query(audience, recipient_id, sector))}


@router.post("/inbox/{notification_id}/{action}", response_model=InboxNotificationDTO, tags=["Notificações Internas"])
async def change_notification(notification_id: uuid.UUID, action: Literal["read", "unread", "archive", "unarchive"],
                              use_case: InboxUseCase = Depends(get_inbox)):
    return await use_case.change(notification_id, action)


# --------------------------------------------------------------------- auditoria

@router.get("/audit-events", response_model=Page[AuditEventDTO], tags=["Auditoria Didática"])
async def search_audit(event_type: Optional[list[EventType]] = Query(None), entity_type: Optional[str] = None,
                       entity_id: Optional[uuid.UUID] = None, patient_id: Optional[uuid.UUID] = None,
                       date_from: Optional[date] = None, date_to: Optional[date] = None,
                       limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                       use_case: AuditUseCase = Depends(get_audit)):
    return await use_case.search(AuditFilters(
        event_types=event_type or [], entity_type=entity_type, entity_id=entity_id, patient_id=patient_id,
        date_from=datetime.combine(date_from, time.min) if date_from else None,
        date_to=datetime.combine(date_to, time.max) if date_to else None, limit=limit, offset=offset))


@router.get("/audit-events/counts", tags=["Auditoria Didática"], summary="Quantidade de eventos por tipo")
async def audit_counts(date_from: Optional[date] = None, use_case: AuditUseCase = Depends(get_audit)):
    return await use_case.counts(datetime.combine(date_from, time.min) if date_from else None)
