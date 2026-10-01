from typing import Optional, List
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.future import select as select_future

from app.domain.entities.role import Role
from app.domain.entities.permission import Permission
from app.application.interfaces.role_repository import RoleRepository
from app.infrastructure.persistence.models.role_models import RoleModel, PermissionModel, user_roles

class SQLAlchemyRoleRepository(RoleRepository):
    """
    Implementação concreta do RoleRepository utilizando SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_role(self, role: Role) -> Role:
        # 1. Garantir que as permissões associadas existam no banco
        permissions_models = []
        for perm in role.permissions:
            # Busca ou cria a permissão
            result = await self.session.execute(
                select(PermissionModel).where(PermissionModel.code == perm.code)
            )
            perm_model = result.scalar_one_or_none()
            if not perm_model:
                perm_model = PermissionModel(code=perm.code, description=perm.description)
                self.session.add(perm_model)
                await self.session.flush()
            permissions_models.append(perm_model)

        # 2. Salva o papel
        db_role = RoleModel(
            id=role.id or uuid.uuid4(),
            name=role.name,
            description=role.description,
            permissions=permissions_models
        )

        self.session.add(db_role)
        await self.session.flush()

        role.id = db_role.id
        return role

    async def get_role_by_id(self, role_id: uuid.UUID) -> Optional[Role]:
        # Usamos select with_joined ou similar para carregar as permissões
        # Para simplicidade neste exemplo, carregamos o modelo e convertemos
        result = await self.session.execute(
            select(RoleModel).where(RoleModel.id == role_id)
        )
        db_role = result.scalar_one_or_none()

        if not db_role:
            return None

        # Mapeamento para Domínio
        return Role(
            id=db_role.id,
            name=db_role.name,
            description=db_role.description,
            permissions=[
                Permission(id=p.id, code=p.code, description=p.description)
                for p in db_role.permissions
            ]
        )

    async def get_permissions_for_user(self, user_id: uuid.UUID) -> List[str]:
        """
        Consulta complexa para recuperar todos os códigos de permissão
        de um usuário atravessando: User -> Role -> Permission.
        """
        stmt = (
            select(PermissionModel.code)
            .join(user_roles)
            .join(RoleModel)
            .join(RoleModel.permissions)
            .where(user_roles.c.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def save_permission(self, permission: Permission) -> Permission:
        db_perm = PermissionModel(
            id=permission.id or uuid.uuid4(),
            code=permission.code,
            description=permission.description
        )
        self.session.add(db_perm)
        await self.session.flush()
        permission.id = db_perm.id
        return permission

    async def assign_role_to_user(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        from app.infrastructure.persistence.models.role_models import user_roles
        # Insere a tupla na tabela de associação N:N
        stmt = user_roles.insert().values(user_id=user_id, role_id=role_id)
        await self.session.execute(stmt)
        await self.session.flush()
