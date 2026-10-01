from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import uuid
import re

@dataclass
class Patient:
    """
    Entidade de Domínio Patient.
    Representa as regras de negócio de um paciente no sistema HealthOS.
    """
    full_name: str
    birth_date: datetime
    cpf: str
    gender: str
    insurance_provider: Optional[str] = None
    insurance_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        self.validate()

    def validate(self):
        """Valida as regras básicas de negócio da entidade Patient."""
        if not self._is_valid_cpf(self.cpf):
            raise ValueError(f"CPF inválido: {self.cpf}")

        if self.birth_date > datetime.now():
            raise ValueError("A data de nascimento não pode ser no futuro.")

    def _is_valid_cpf(self, cpf: str) -> bool:
        clean_cpf = re.sub(r'\D', '', cpf)
        if len(clean_cpf) != 11 or clean_cpf == clean_cpf[0] * 11:
            return False
        return True

    def update_contact_info(self, phone: Optional[str] = None, email: Optional[str] = None):
        """Regra de negócio para atualizar contatos do paciente."""
        if phone:
            self.phone = phone
        if email:
            self.email = email
