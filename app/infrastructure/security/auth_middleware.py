from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.infrastructure.security.jwt_handler import JWTHandler
from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
from app.infrastructure.persistence.database import get_db
from app.domain.entities.user import User
from app.domain.exceptions.base import DomainException

# O HTTPBearer fornece a interface de "Cadeado" no Swagger UI
security = HTTPBearer()

async def get_current_user(
    auth: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependência do FastAPI que valida o token JWT e retorna o usuário autenticado.
    Funciona como um middleware de autenticação por rota.
    """
    jwt_handler = JWTHandler()
    user_repo = SQLAlchemyUserRepository(session)

    # 1. Decodifica o token
    payload = jwt_handler.get_token_payload(auth.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Extrai o ID do usuário (sub)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token malformado: ID do usuário não encontrado",
        )

    # 3. Busca o usuário no banco para garantir que ele ainda existe e está ativo
    try:
        import uuid
        user = await user_repo.get_by_id(uuid.UUID(user_id))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Erro ao validar identidade do usuário",
        )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inativo ou inexistente",
        )

    return user
