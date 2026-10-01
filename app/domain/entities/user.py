from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import uuid
import re

@dataclass
class User:
    """
    Entidade de Domínio User.
    Representa as regras de negócio de um usuário no sistema HealthOS.
    """
    full_name: str
    email: str
    cpf: str
    password_hash: str
    phone: str
    is_active: bool = True
    id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        self.validate()

    def validate(self):
        """Valida as regras básicas de negócio da entidade User."""
        if not self._is_valid_email(self.email):
            raise ValueError(f"E-mail inválido: {self.email}")

        if not self._is_valid_cpf(self.cpf):
            raise ValueError(f"CPF inválido: {self.cpf}")

        if len(self.full_name) < 3:
            raise ValueError("O nome completo deve ter pelo menos 3 caracteres.")

    def _is_valid_email(self, email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def _is_valid_cpf(self, cpf: str) -> bool:
        # Remove caracteres não numéricos
        clean_cpf = re.sub(r'\D', '', cpf)
        if len(clean_cpf) != 11:
            return False

        # Verifica se todos os dígitos são iguais (CPF inválido)
        if clean_cpf == clean_cpf[0] * 11:
            return False

        return True

    def deactivate(self):
        """Regra de negócio para inativar usuário (soft delete)."""
        self.is_active = False

    def activate(self):
        """Regra de negócio para reativar usuário."""
        self.is_active = True
