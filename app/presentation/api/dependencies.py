"""Dependências compartilhadas pelos routers."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.events import InProcessPublisher
from app.infrastructure.events import build_publisher
from app.infrastructure.persistence.database import get_db


async def get_events(session: AsyncSession = Depends(get_db)) -> InProcessPublisher:
    """Um publicador por requisição, ligado à mesma sessão usada pelos casos de uso."""
    return build_publisher(session)
