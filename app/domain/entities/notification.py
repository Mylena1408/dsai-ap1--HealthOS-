from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Any
import uuid
from datetime import datetime

class NotificationType(Enum):
    """Tipos de notificações suportadas pelo sistema."""
    APPOINTMENT_REMINDER = "LEMBRETE_CONSULTA"
    CRITICAL_ALERT = "ALERTA_CRITICO"
    BILLING_REMINDER = "LEMBRETE_FATURA"
    SYSTEM_UPDATE = "ATUALIZACAO_SISTEMA"
    TRIAGE_UPDATE = "ATUALIZACAO_TRIAGEM"

class NotificationChannel(Enum):
    """Canais de entrega de notificações."""
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH_NOTIFICATION"
    IN_APP = "IN_APP"

class NotificationStatus(Enum):
    """Status de entrega da notificação."""
    PENDING = "PENDENTE"
    SENT = "ENVIADA"
    DELIVERED = "ENTREGUE"
    FAILED = "FALHA"
    READ = "LIDA"

@dataclass
class Notification:
    """
    Entidade de Domínio Notification.
    Representa uma mensagem enviada a um usuário ou paciente.
    """
    id: Optional[uuid.UUID] = None
    user_id: uuid.UUID = field(default=None) # Pode ser médico ou admin
    patient_id: Optional[uuid.UUID] = None    # Se a notificação for para o paciente
    type: NotificationType = field(default=NotificationType.SYSTEM_UPDATE)
    channel: NotificationChannel = field(default=NotificationChannel.IN_APP)
    title: str = field(default="")
    message: str = field(default="")
    priority: int = field(default=1) # 1: Normal, 2: Alta, 3: Crítica
    status: NotificationStatus = NotificationStatus.PENDING

    # Metadados para links profundos (ex: ID da fatura ou ID da consulta)
    metadata: dict = field(default_factory=dict)

    created_at: datetime = field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

    def mark_as_read(self):
        """Marca a notificação como lida."""
        self.status = NotificationStatus.READ
        self.read_at = datetime.now()

    def update_status(self, new_status: NotificationStatus):
        """Atualiza o status de entrega."""
        self.status = new_status
        if new_status == NotificationStatus.SENT:
            self.sent_at = datetime.now()
