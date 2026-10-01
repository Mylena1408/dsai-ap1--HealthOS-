from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from typing import List

from app.application.dtos.user_dto import UserCreateDTO, UserUpdateDTO, UserResponseDTO
from app.application.use_cases.create_user_use_case import CreateUserUseCase
from app.application.use_cases.manage_user_use_case import ManageUserUseCase
from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
from app.infrastructure.security.auth_middleware import get_current_user
from app.infrastructure.security.permission_checker import PermissionChecker
from app.infrastructure.persistence.database import get_db

router = APIRouter(prefix="/users", tags=["Administração de Usuários"])

# Dependência para injeção do repositório
async def get_user_repo(session: AsyncSession = Depends(get_db)):
    return SQLAlchemyUserRepository(session)

@router.post("/", response_model=UserResponseDTO, status_code=status.HTTP_201_CREATED,
              dependencies=[Depends(PermissionChecker(["user:create"]))])
async def create_user(
    request: UserCreateDTO,
    repo: SQLAlchemyUserRepository = Depends(get_user_repo)
):
    try:
        use_case = CreateUserUseCase(repo)
        return await use_case.execute(request)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.get("/", response_model=List[UserResponseDTO],
             dependencies=[Depends(PermissionChecker(["user:read"]))])
async def list_users(
    repo: SQLAlchemyUserRepository = Depends(get_user_repo)
):
    use_case = ManageUserUseCase(repo)
    return await use_case.list_all_users()

@router.patch("/{user_id}", response_model=UserResponseDTO,
              dependencies=[Depends(PermissionChecker(["user:update"]))])
async def update_user(
    user_id: uuid.UUID,
    request: UserUpdateDTO,
    repo: SQLAlchemyUserRepository = Depends(get_user_repo)
):
    try:
        use_case = ManageUserUseCase(repo)
        return await use_case.update_user(user_id, request)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(PermissionChecker(["user:delete"]))])
async def deactivate_user(
    user_id: uuid.UUID,
    repo: SQLAlchemyUserRepository = Depends(get_user_repo)
):
    try:
        use_case = ManageUserUseCase(repo)
        await use_case.deactivate_user(user_id)
        return None
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
