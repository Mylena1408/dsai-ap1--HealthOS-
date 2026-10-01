from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Any
import uuid

@dataclass
class AuditLog:
    """
    Entidade de Domínio AuditLog.
    Representa o registro de uma alteração no sistema para fins de conformidade.
    """
    user_id: uuid.UUID
    timestamp: datetime
    action: str  # CREATE, UPDATE, DELETE
    resource: str  # Nome da classe/tabela afetada
    resource_id: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    ip_address: Optional[str] = None
    id: Optional[int] = None
