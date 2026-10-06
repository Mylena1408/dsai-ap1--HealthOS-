"""Middleware que registra cada requisição no log e nas métricas."""
import logging
import time

from starlette.requests import Request

from app.infrastructure.observability.metrics import metrics

logger = logging.getLogger("healthos.http")

# Arquivos estáticos e o próprio /metrics poluiriam as estatísticas da API.
_IGNORED_PREFIXES = ("/static", "/metrics", "/favicon.ico")


def _route_template(request: Request) -> str:
    """Usa o padrão da rota (/patients/{id}) para não criar uma métrica por UUID."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or "<não roteado>"


async def request_metrics_middleware(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        path = request.url.path
        if not path.startswith(_IGNORED_PREFIXES):
            metrics.record(request.method, _route_template(request), status_code, duration_ms)
            log = logger.warning if status_code >= 500 else logger.info
            log("%s %s -> %s (%.1f ms)", request.method, path, status_code, duration_ms)
