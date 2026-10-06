"""Agendador em processo para a avaliação periódica de alertas.

Didático e simples: uma tarefa asyncio no mesmo processo da API. Em produção com
várias instâncias, isso viraria um job externo (cron, fila) para não duplicar execuções.
"""
import asyncio
import logging
from contextlib import suppress
from typing import Optional

from app.application.use_cases.alert_engine_use_case import AlertEngineUseCase
from app.infrastructure.persistence.database import AsyncSessionLocal
from app.infrastructure.persistence.repositories.sqlalchemy_alert_detector import SQLAlchemyAlertDetector
from app.infrastructure.persistence.repositories.sqlalchemy_engagement_repository import (
    SQLAlchemySystemAlertRepository,
)
from app.infrastructure.events import build_publisher

logger = logging.getLogger("healthos.alerts")


async def evaluate_alerts_once() -> None:
    async with AsyncSessionLocal() as session:
        engine = AlertEngineUseCase(SQLAlchemySystemAlertRepository(session), SQLAlchemyAlertDetector(session),
                                    build_publisher(session))
        report = await engine.evaluate()
        await session.commit()
    logger.info("Alertas avaliados: %s abertos, %s resolvidos automaticamente, %s agravados",
                report.opened, report.auto_resolved, report.escalated)


class AlertScheduler:
    def __init__(self, interval_minutes: int):
        self.interval = interval_minutes * 60
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if self.interval > 0 and self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await evaluate_alerts_once()
            except Exception:  # uma falha não deve derrubar o agendador
                logger.exception("Falha ao avaliar alertas")
            await asyncio.sleep(self.interval)
