from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import uuid

@dataclass
class Permission:
    """
    Entidade de Domínio Permission.
    Representa uma permissão granular dentro do sistema (ex: 'patient:read').
    """
    code: str
    description: str
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        if not self.code or ":" not in self.code:
            raise ValueError("O código da permissão deve seguir o padrão 'modulo:acao' (ex: 'user:create').")
