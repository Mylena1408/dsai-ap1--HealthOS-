from abc import ABC, abstractmethod
from typing import List, Optional
import uuid
from app.domain.entities.user import User

class UserRepository(ABC):
    """
    Interface de Repositório para Usuários.
    Define o contrato de persistência que a camada de infraestrutura deve implementar.
    """

    @abstractmethod
    async def save(self, user: User) -> User:
        """Persiste um usuário no banco de dados."""
        pass

    @abstractmethod
    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Busca um usuário pelo seu ID único."""
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        """Busca um usuário pelo seu endereço de e-mail."""
        pass

    @abstractmethod
    async def get_by_cpf(self, cpf: str) -> Optional[User]:
        """Busca um usuário pelo seu CPF."""
        pass

    @abstractmethod
    async def update(self, user: User) -> User:
        """Atualiza os dados de um usuário existente."""
        pass

    @abstractmethod
    async def list_all(self) -> List[User]:
        """Retorna todos os usuários cadastrados."""
        pass
