from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.application.dtos.auth_dto import LoginRequestDTO, AuthResponseDTO
from app.application.use_cases.authenticate_user_use_case import AuthenticateUserUseCase
from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
from app.infrastructure.security.jwt_handler import JWTHandler
from app.infrastructure.persistence.database import get_db
from app.domain.exceptions.base import DomainException

router = APIRouter(prefix="/auth", tags=["Autenticação"])

async def get_auth_use_case(session: AsyncSession = Depends(get_db)):
    # NOTA: O 'session' será injetado corretamente na T2.6/T2.7
    # Por enquanto, simulamos a dependência
    repo = SQLAlchemyUserRepository(session)
    jwt = JWTHandler()
    return AuthenticateUserUseCase(repo, jwt)

@router.post("/login", response_model=AuthResponseDTO)
async def login(
    request: LoginRequestDTO,
    use_case: AuthenticateUserUseCase = Depends(get_auth_use_case)
):
    try:
        return await use_case.execute(request)
    except DomainException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno no servidor"
        )
