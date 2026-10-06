"""Exceções de domínio genéricas usadas pelos módulos novos.

Cada uma corresponde a um status HTTP (ver app/presentation/api/error_handlers.py),
o que evita repetir blocos try/except em todos os endpoints.
"""
from app.domain.exceptions.base import DomainException


class EntityNotFoundError(DomainException):
    """O recurso solicitado não existe (HTTP 404)."""

    def __init__(self, entity: str, entity_id: object):
        super().__init__(f"{entity} não encontrado(a): {entity_id}")


class BusinessRuleViolation(DomainException):
    """Os dados ou a operação violam uma regra de negócio (HTTP 400)."""


class ConflictError(DomainException):
    """A operação conflita com o estado atual dos dados (HTTP 409)."""


class ServiceUnavailableError(DomainException):
    """Um serviço externo necessário à operação está indisponível (HTTP 503)."""


class InvalidTransitionError(ConflictError):
    """Transição de estado não permitida pela máquina de estados (HTTP 409)."""

    def __init__(self, entity: str, current: str, target: str):
        super().__init__(f"{entity}: transição de '{current}' para '{target}' não é permitida.")
