from fastapi import Depends, HTTPException, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.security.auth_middleware import get_current_user
from app.domain.entities.user import User
from app.infrastructure.persistence.repositories.sqlalchemy_role_repository import SQLAlchemyRoleRepository

class PermissionChecker:
    """
    Classe utilitária para verificar se um usuário possui permissões específicas.
    Implementada como uma Factory para permitir a verificação de diferentes permissões em cada endpoint.
    """
    def __init__(self, required_permissions: List[str]):
        self.required_permissions = required_permissions

    async def __call__(
        self,
        user: User = Depends(get_current_user),
        # Nota: A injeção de session será globalizada posteriormente
        session: AsyncSession = Depends(lambda: None)
    ):
        """
        Valida se o usuário autenticado possui TODAS as permissões requeridas.
        """
        role_repo = SQLAlchemyRoleRepository(session)

        # Recupera todas as permissões do usuário através de seus papéis
        user_permissions = await role_repo.get_permissions_for_user(user.id)

        # Verifica se todas as permissões requeridas estão presentes na lista do usuário
        for perm in self.required_permissions:
            if perm not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acesso negado. Permissão necessária: {perm}"
                )

        return True
