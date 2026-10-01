from typing import Tuple
from app.application.interfaces.user_repository import UserRepository
from app.application.dtos.auth_dto import LoginRequestDTO, AuthResponseDTO
from app.infrastructure.security.jwt_handler import JWTHandler
from app.domain.exceptions.user_exceptions import UserDomainException

class AuthenticateUserUseCase:
    """
    Caso de Uso para autenticação de usuários.
    Orquestra a verificação de credenciais e a emissão de tokens.
    """

    def __init__(self, user_repository: UserRepository, jwt_handler: JWTHandler):
        self.user_repository = user_repository
        self.jwt_handler = jwt_handler

    async def execute(self, request: LoginRequestDTO) -> AuthResponseDTO:
        # 1. Busca o usuário pelo e-mail
        user = await self.user_repository.get_by_email(request.email)

        if not user or not user.is_active:
            raise UserDomainException("Credenciais inválidas ou usuário inativo.")

        # 2. Validação de senha (SIMPLIFICADA para fins exemplificativos)
        # Em produção, aqui usaríamos o PasswordHasher
        if user.password_hash != request.password:
            raise UserDomainException("Credenciais inválidas.")

        # 3. Geração de Tokens
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "full_name": user.full_name
        }

        access_token = self.jwt_handler.create_access_token(data=payload)
        refresh_token = self.jwt_handler.create_refresh_token(data=payload)

        return AuthResponseDTO(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=str(user.id),
            full_name=user.full_name
        )
