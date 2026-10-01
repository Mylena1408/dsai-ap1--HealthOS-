from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
import uuid

class UserCreateDTO(BaseModel):
    """DTO para a criação de um novo usuário."""
    full_name: str = Field(..., min_length=3, max_length=255)
    email: EmailStr
    cpf: str = Field(..., pattern=r'^\d{3}\.\d{3}\.\d{3}-\d{2}$|^\d{11}$')
    password: str = Field(..., min_length=6)
    phone: Optional[str] = None

class UserUpdateDTO(BaseModel):
    """DTO para atualização de dados do usuário."""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponseDTO(BaseModel):
    """DTO para retorno de dados do usuário (omite a senha)."""
    id: uuid.UUID
    full_name: str
    email: EmailStr
    cpf: str
    phone: Optional[str]
    is_active: bool
