from typing import List


class PermissionChecker:
    """Bypass de autenticação e permissões para demonstração pública."""

    def __init__(self, required_permissions: List[str]):
        self.required_permissions = required_permissions

    async def __call__(self) -> bool:
        # As rotas seguem públicas, sem exigir JWT ou papéis de usuário.
        return True
