from pydantic import BaseModel, EmailStr

class LoginRequestDTO(BaseModel):
    """DTO para entrada de dados de login."""
    email: EmailStr
    password: str

class AuthResponseDTO(BaseModel):
    """DTO para resposta de autenticação."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
