from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from pydantic import BaseModel
from app.infrastructure.persistence.repositories.sqlalchemy_notification_repository import SQLAlchemyNotificationRepository
from app.application.use_cases.notification_use_case import NotificationUseCase
from app.infrastructure.security.permission_checker import PermissionChecker
from app.infrastructure.persistence.database import get_db
from app.domain.exceptions.base import DomainException

class NotificationRequestDTO(BaseModel):
    user_id: Optional[uuid.UUID] = None
    patient_id: Optional[uuid.UUID] = None
    type: str
    title: str
    message: str
    channel: str = "IN_APP"
    priority: int = 1
    metadata: Optional[dict] = None

LEGACY = ("Legado: notificações separadas da caixa de entrada usada pelas telas. Use GET /inbox "
          "(ver docs/INTEGRACOES.md, L4).")

router = APIRouter(prefix="/notifications", tags=["Notificações"])

async def get_notification_use_case(session: AsyncSession = Depends(get_db)):
    repo = SQLAlchemyNotificationRepository(session)
    return NotificationUseCase(repo)

@router.post("/send", description=LEGACY, status_code=status.HTTP_201_CREATED,
              dependencies=[Depends(PermissionChecker(["notification:write"]))])
async def send_notification(request: NotificationRequestDTO, use_case: NotificationUseCase = Depends(get_notification_use_case)):
    try:
        from app.domain.entities.notification import NotificationType, NotificationChannel
        return await use_case.send_notification(
            user_id=request.user_id,
            patient_id=request.patient_id,
            type=NotificationType(request.type),
            title=request.title,
            message=request.message,
            channel=NotificationChannel(request.channel),
            priority=request.priority,
            metadata=request.metadata
        )
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.get("/me", description=LEGACY, dependencies=[Depends(PermissionChecker(["notification:read"]))])
async def get_my_notifications(user_id: Optional[uuid.UUID] = None,
                              patient_id: Optional[uuid.UUID] = None,
                              use_case: NotificationUseCase = Depends(get_notification_use_case)):
    try:
        return await use_case.get_my_notifications(user_id=user_id, patient_id=patient_id)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.patch("/{notification_id}/read", description=LEGACY,
              dependencies=[Depends(PermissionChecker(["notification:write"]))])
async def mark_as_read(notification_id: uuid.UUID, use_case: NotificationUseCase = Depends(get_notification_use_case)):
    success = await use_case.mark_as_read(notification_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notificação não encontrada.")
    return {"message": "Notificação marcada como lida."}
