from typing import Optional
from typing import List
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.domain.entities.user import User
from app.application.interfaces.user_repository import UserRepository
from app.infrastructure.persistence.models.user_model import UserModel

class SQLAlchemyUserRepository(UserRepository):
    """
    Implementação concreta do UserRepository utilizando SQLAlchemy e PostgreSQL.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, user: User) -> User:
        # Mapeia a Entidade de Domínio -> Modelo de Persistência
        db_user = UserModel(
            id=user.id or uuid.uuid4(),
            email=user.email,
            password_hash=user.password_hash,
            full_name=user.full_name,
            cpf=user.cpf,
            phone=user.phone,
            is_active=user.is_active
        )
        self.session.add(db_user)
        await self.session.flush() # Garante a atribuição do ID se for gerado pelo DB

        user.id = db_user.id
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
        db_user = result.scalar_one_or_none()

        if not db_user:
            return None

        return self._map_to_domain(db_user)

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(select(UserModel).where(UserModel.email == email))
        db_user = result.scalar_one_or_none()

        if not db_user:
            return None

        return self._map_to_domain(db_user)

    async def get_by_cpf(self, cpf: str) -> Optional[User]:
        result = await self.session.execute(select(UserModel).where(UserModel.cpf == cpf))
        db_user = result.scalar_one_or_none()

        if not db_user:
            return None

        return self._map_to_domain(db_user)

    async def update(self, user: User) -> User:
        db_user = await self.get_by_id(user.id)
        if not db_user:
            return None

        # Atualizamos os atributos no modelo SQLAlchemy
        db_user_model = UserModel(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            full_name=user.full_name,
            cpf=user.cpf,
            phone=user.phone,
            is_active=user.is_active
        )

        await self.session.merge(db_user_model)
        await self.session.flush()

        return user

    async def list_all(self) -> List[User]:
        result = await self.session.execute(select(UserModel))
        db_users = result.scalars().all()
        return [self._map_to_domain(u) for u in db_users]

    def _map_to_domain(self, db_user: UserModel) -> User:
        """Método privado para converter o Modelo de DB para a Entidade de Domínio."""
        from app.domain.entities.user import User # Import local para evitar circularidade
        return User(
            id=db_user.id,
            email=db_user.email,
            full_name=db_user.full_name,
            cpf=db_user.cpf,
            password_hash=db_user.password_hash,
            phone=db_user.phone,
            is_active=db_user.is_active,
            created_at=db_user.created_at,
            updated_at=db_user.updated_at
        )
