from typing import List
import uuid
from app.application.interfaces.user_repository import UserRepository
from app.application.dtos.user_dto import UserUpdateDTO, UserResponseDTO
from app.domain.exceptions.user_exceptions import UserDomainException
from app.domain.exceptions.base import DomainException

class ManageUserUseCase:
    """
    Caso de Uso para gestão de usuários existentes.
    """

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def list_all_users(self) -> List[UserResponseDTO]:
        # Para simplificar, usaremos um método fictício de listagem no repositório
        # Na implementação final, adicionaríamos 'list_all' ao UserRepository
        if hasattr(self.user_repository, 'list_all'):
            users = await self.user_repository.list_all()
            return [
                UserResponseDTO(
                    id=u.id, full_name=u.full_name, email=u.email,
                    cpf=u.cpf, phone=u.phone, is_active=u.is_active
                ) for u in users
            ]
        return []

    async def update_user(self, user_id: uuid.UUID, request: UserUpdateDTO) -> UserResponseDTO:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise UserDomainException(f"Usuário {user_id} não encontrado.")

        if request.full_name: user.full_name = request.full_name
        if request.phone: user.phone = request.phone
        if request.is_active is not None: user.is_active = request.is_active

        updated_user = await self.user_repository.update(user)

        return UserResponseDTO(
            id=updated_user.id,
            full_name=updated_user.full_name,
            email=updated_user.email,
            cpf=updated_user.cpf,
            phone=updated_user.phone,
            is_active=updated_user.is_active
        )

    async def deactivate_user(self, user_id: uuid.UUID) -> bool:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise UserDomainException(f"Usuário {user_id} não encontrado.")

        user.deactivate()
        await self.user_repository.update(user)
        return True
