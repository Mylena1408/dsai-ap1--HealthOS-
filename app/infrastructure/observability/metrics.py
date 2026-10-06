"""Métricas de requisições mantidas em memória.

Didático e propositalmente simples: os contadores vivem no processo e são
zerados a cada reinício. Em produção usaríamos Prometheus/OpenTelemetry.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class RouteStats:
    count: int = 0
    errors: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    status_codes: dict[int, int] = field(default_factory=dict)

    def record(self, status_code: int, duration_ms: float) -> None:
        self.count += 1
        if status_code >= 500:
            self.errors += 1
        self.total_ms += duration_ms
        self.max_ms = max(self.max_ms, duration_ms)
        self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1

    def as_dict(self) -> dict:
        return {
            "count": self.count,
            "errors": self.errors,
            "avg_ms": round(self.total_ms / self.count, 2) if self.count else 0.0,
            "max_ms": round(self.max_ms, 2),
            "status_codes": {str(code): total for code, total in sorted(self.status_codes.items())},
        }


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._routes: dict[str, RouteStats] = {}
        self.started_at = time.time()

    def record(self, method: str, route: str, status_code: int, duration_ms: float) -> None:
        key = f"{method} {route}"
        with self._lock:
            self._routes.setdefault(key, RouteStats()).record(status_code, duration_ms)

    def uptime_seconds(self) -> float:
        return time.time() - self.started_at

    def snapshot(self) -> dict:
        with self._lock:
            routes = {key: stats.as_dict() for key, stats in sorted(self._routes.items())}
        total = sum(r["count"] for r in routes.values())
        errors = sum(r["errors"] for r in routes.values())
        return {
            "uptime_seconds": round(self.uptime_seconds(), 1),
            "requests_total": total,
            "errors_total": errors,
            "error_rate": round(errors / total, 4) if total else 0.0,
            "routes": routes,
        }

    def reset(self) -> None:
        with self._lock:
            self._routes.clear()


metrics = MetricsRegistry()
