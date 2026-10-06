"""Tradução das exceções de domínio dos módulos novos para respostas HTTP.

Apenas as subclasses de app.domain.exceptions.common são registradas; os
routers legados continuam tratando suas próprias exceções como antes.
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions.common import BusinessRuleViolation, ConflictError, EntityNotFoundError

_STATUS_BY_EXCEPTION = {
    EntityNotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,  # inclui InvalidTransitionError
    BusinessRuleViolation: status.HTTP_400_BAD_REQUEST,
}


def register_error_handlers(app: FastAPI) -> None:
    for exception_class, status_code in _STATUS_BY_EXCEPTION.items():
        async def handler(_: Request, exc: Exception, code: int = status_code) -> JSONResponse:
            return JSONResponse(status_code=code, content={"detail": exc.message})
        app.add_exception_handler(exception_class, handler)
