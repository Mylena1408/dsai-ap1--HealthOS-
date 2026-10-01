class DomainException(Exception):
    """Classe base para todas as exceções de domínio do HealthOS."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
