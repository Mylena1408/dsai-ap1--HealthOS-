from app.application.interfaces.user_repository import UserRepository
from app.application.dtos.user_dto import UserCreateDTO, UserResponseDTO
from app.domain.entities.user import User
from app.domain.exceptions.user_exceptions import UserAlreadyExistsError

class CreateUserUseCase:
    """
    Caso de Uso para criação de novos usuários no sistema.
    Orquestra a validação de unicidade e a persistência.
    """

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def execute(self, request: UserCreateDTO) -> UserResponseDTO:
        # 1. Validação de Unicidade: E-mail já existe?
        existing_email = await self.user_repository.get_by_email(request.email)
        if existing_email:
            raise UserAlreadyExistsError("email", request.email)

        # 2. Validação de Unicidade: CPF já existe?
        existing_cpf = await self.user_repository.get_by_cpf(request.cpf)
        if existing_cpf:
            raise UserAlreadyExistsError("cpf", request.cpf)

        # 3. Criação da Entidade de Domínio
        # NOTA: A senha é salva em texto puro por ser um projeto exemplificativo
        user = User(
            full_name=request.full_name,
            email=request.email,
            cpf=request.cpf,
            password_hash=request.password,
            phone=request.phone
        )

        # 4. Persistência via Repositório
        created_user = await self.user_repository.save(user)

        # 5. Retorno via DTO
        return UserResponseDTO(
            id=created_user.id,
            full_name=created_user.full_name,
            email=created_user.email,
            cpf=created_user.cpf,
            phone=created_user.phone,
            is_active=created_user.is_active
        )
