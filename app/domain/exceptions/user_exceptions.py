from app.domain.exceptions.base import DomainException

class UserDomainException(DomainException):
    """Classe base para exceções relacionadas ao domínio de Usuário."""
    pass

class UserAlreadyExistsError(UserDomainException):
    """Lançada quando tenta-se criar um usuário com e-mail ou CPF já cadastrado."""
    def __init__(self, field: str, value: str):
        super().__init__(f"Usuário com {field} '{value}' já existe no sistema.")

class InvalidUserDataError(UserDomainException):
    """Lançada quando os dados do usuário não atendem aos critérios de validação."""
    pass
