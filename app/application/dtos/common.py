from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Resposta paginada padrão dos módulos novos."""
    items: list[T]
    total: int
    limit: int
    offset: int
