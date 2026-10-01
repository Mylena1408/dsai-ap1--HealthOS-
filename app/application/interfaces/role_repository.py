from abc import ABC, abstractmethod
from typing import Optional, List
import uuid
from app.domain.entities.role import Role
from app.domain.entities.permission import Permission

class RoleRepository(ABC):
    """
    Interface de Repositório para Papéis e Permissões.
    """

    @abstractmethod
    async def save_role(self, role: Role) -> Role:
        """Persiste um papel e suas permissões associadas."""
        pass

    @abstractmethod
    async def get_role_by_id(self, role_id: uuid.UUID) -> Optional[Role]:
        """Busca um papel e carrega suas permissões."""
        pass

    @abstractmethod
    async def get_permissions_for_user(self, user_id: uuid.UUID) -> List[str]:
        """Retorna a lista de todos os códigos de permissão de um usuário (via seus papéis)."""
        pass

    @abstractmethod
    async def save_permission(self, permission: Permission) -> Permission:
        """Persiste uma permissão granular."""
        pass

    @abstractmethod
    async def assign_role_to_user(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        """Vincula um papel a um usuário."""
        pass
