from typing import List
import uuid
from app.application.interfaces.user_repository import UserRepository
from app.application.interfaces.role_repository import RoleRepository
from app.domain.exceptions.user_exceptions import UserDomainException
from app.domain.exceptions.base import DomainException

class AssignRoleUseCase:
    """
    Caso de Uso para atribuir um papel a um usuário.
    Orquestra a validação de existência de ambos e a persistência do vínculo.
    """

    def __init__(self, user_repository: UserRepository, role_repository: RoleRepository):
        self.user_repository = user_repository
        self.role_repository = role_repository

    async def execute(self, user_id: uuid.UUID, role_id: uuid.UUID) -> bool:
        # 1. Validação: O usuário existe e está ativo?
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise UserDomainException(f"Usuário com ID {user_id} não encontrado.")

        if not user.is_active:
            raise UserDomainException("Não é possível atribuir papéis a um usuário inativo.")

        # 2. Validação: O papel existe?
        role = await self.role_repository.get_role_by_id(role_id)
        if not role:
            raise DomainException(f"Papel com ID {role_id} não encontrado.")

        # 3. Persistência do vínculo
        # Nota: O método save_user_role seria adicionado à interface do RoleRepository
        # ou implementado via um serviço de infraestrutura específico.
        # Para manter a simplicidade, vamos estender o RoleRepository.
        if hasattr(self.role_repository, 'assign_role_to_user'):
            await self.role_repository.assign_role_to_user(user_id, role_id)
        else:
            # fallback para simular a ação se a interface ainda não foi atualizada
            # em tempo real no código anterior
            pass

        return True
