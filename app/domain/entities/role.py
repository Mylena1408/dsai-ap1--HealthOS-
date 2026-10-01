from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import uuid
from app.domain.entities.permission import Permission

@dataclass
class Role:
    """
    Entidade de Domínio Role.
    Representa um papel ou perfil de acesso no sistema (ex: 'ADMIN', 'MEDICO').
    """
    name: str
    description: str
    permissions: List[Permission] = field(default_factory=list)
    id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None

    def add_permission(self, permission: Permission):
        """Adiciona uma permissão ao papel, evitando duplicatas."""
        if permission not in self.permissions:
            self.permissions.append(permission)

    def remove_permission(self, permission_code: str):
        """Remove uma permissão baseada no código."""
        self.permissions = [p for p in self.permissions if p.code != permission_code]

    def has_permission(self, permission_code: str) -> bool:
        """Verifica se este papel possui uma determinada permissão."""
        return any(p.code == permission_code for p in self.permissions)
