from typing import List, Optional
import uuid
from datetime import datetime
from app.application.interfaces.notification_repository import NotificationRepository
from app.domain.entities.notification import Notification, NotificationType, NotificationChannel, NotificationStatus
from app.domain.exceptions.base import DomainException

class NotificationUseCase:
    """
    Caso de Uso para a gestão de notificações.
    Orquestra a criação, disparo e leitura de alertas para médicos e pacientes.
    """

    def __init__(self, notification_repository: NotificationRepository):
        self.notification_repository = notification_repository

    async def send_notification(self,
                                user_id: Optional[uuid.UUID] = None,
                                patient_id: Optional[uuid.UUID] = None,
                                type: NotificationType = NotificationType.SYSTEM_UPDATE,
                                title: str = "",
                                message: str = "",
                                channel: NotificationChannel = NotificationChannel.IN_APP,
                                priority: int = 1,
                                metadata: Optional[dict] = None) -> Notification:
        """
        Cria e agenda uma notificação para ser enviada.
        """
        if not user_id and not patient_id:
            raise DomainException(message="A notificação deve ter um destinatário (usuário ou paciente).")

        notification = Notification(
            user_id=user_id,
            patient_id=patient_id,
            type=type,
            title=title,
            message=message,
            channel=channel,
            priority=priority,
            status=NotificationStatus.PENDING,
            metadata=metadata or {}
        )

        # Aqui, em um sistema real, dispararíamos um evento para um Worker de envio (Celery/RabbitMQ)
        # Para este projeto, persistimos como PENDING e simulamos o envio imediato para canais IN_APP
        if channel == NotificationChannel.IN_APP:
            notification.update_status(NotificationStatus.SENT)

        return await self.notification_repository.save(notification)

    async def notify_critical_triage(self, patient_id: uuid.UUID, nurse_id: uuid.UUID, priority_level: str):
        """
        Notifica a equipe médica sobre uma triagem de alta prioridade (Ex: RED).
        Este método seria chamado pelo TriageUseCase.
        """
        # Simulamos a busca por médicos de plantão (em um sistema real, buscaríamos no Schedule)
        # Aqui enviamos para um admin/médico genérico para exemplo
        return await self.send_notification(
            user_id=nurse_id,
            type=NotificationType.CRITICAL_ALERT,
            title="ALERTA CRÍTICO: Triagem Vermelha",
            message=f"Paciente {patient_id} foi classificado como {priority_level} e requer atendimento imediato!",
            priority=3,
            channel=NotificationChannel.PUSH,
            metadata={"patient_id": str(patient_id), "priority": priority_level}
        )

    async def notify_appointment_reminder(self, patient_id: uuid.UUID, appointment_id: uuid.UUID, date_time: datetime):
        """
        Envia lembrete de consulta para o paciente.
        """
        return await self.send_notification(
            patient_id=patient_id,
            type=NotificationType.APPOINTMENT_REMINDER,
            title="Lembrete de Consulta",
            message=f"Você tem uma consulta agendada para {date_time.strftime('%d/%m/%Y %H:%M')}.",
            priority=1,
            channel=NotificationChannel.SMS,
            metadata={"appointment_id": str(appointment_id)}
        )

    async def mark_as_read(self, notification_id: uuid.UUID) -> bool:
        """
        Marca uma notificação específica como lida.
        """
        return await self.notification_repository.mark_as_read(notification_id)

    async def get_my_notifications(self, user_id: Optional[uuid.UUID] = None,
                                   patient_id: Optional[uuid.UUID] = None) -> List[Notification]:
        """
        Recupera as notificações não lidas do usuário ou paciente.
        """
        if user_id:
            return await self.notification_repository.get_unread_by_user(user_id)
        elif patient_id:
            return await self.notification_repository.get_unread_by_patient(patient_id)
        else:
            raise DomainException(message="Identificador do destinatário é necessário.")
