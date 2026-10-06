"""Publicador de eventos de domínio (síncrono, dentro da transação da requisição)."""
from typing import Awaitable, Callable, Protocol

from app.domain.events import DomainEvent

Handler = Callable[[DomainEvent], Awaitable[None]]


class EventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...


class NullPublisher:
    """Usado quando ninguém precisa reagir (ex.: testes de unidade dos casos de uso)."""

    async def publish(self, event: DomainEvent) -> None:
        return None


class InProcessPublisher:
    """
    Entrega cada evento a todos os manipuladores, em ordem. Como roda na mesma sessão
    de banco da operação, uma falha em um manipulador desfaz a operação inteira —
    auditoria e notificações nunca ficam fora de sincronia com os dados.
    """

    def __init__(self, handlers: list[Handler] | None = None):
        self.handlers = list(handlers or [])
        self.published: list[DomainEvent] = []

    def subscribe(self, handler: Handler) -> None:
        self.handlers.append(handler)

    async def publish(self, event: DomainEvent) -> None:
        self.published.append(event)
        for handler in self.handlers:
            await handler(event)
