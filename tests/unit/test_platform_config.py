"""Configuração que muda entre Windows (desenvolvimento) e Linux (Render)."""
import os

import pytest

import config.settings as settings_module
from app.infrastructure.persistence.database import async_database_url


@pytest.mark.parametrize("url,expected", [
    ("sqlite:///./app.db", "sqlite+aiosqlite:///./app.db"),
    ("sqlite+aiosqlite:///./app.db", "sqlite+aiosqlite:///./app.db"),
    ("postgres://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),           # formato do Render
    ("postgresql://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
    ("postgresql+asyncpg://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
    ("postgresql://u:p@host/db?sslmode=require", "postgresql+asyncpg://u:p@host/db?ssl=require"),
])
def test_database_url_uses_async_drivers(url, expected):
    assert async_database_url(url) == expected


def test_timezone_is_a_no_op_without_tzset(monkeypatch):
    monkeypatch.delattr(settings_module.time, "tzset", raising=False)  # como no Windows
    assert settings_module.apply_timezone("America/Belem") is False


def test_timezone_is_applied_on_unix(monkeypatch):
    calls = []
    monkeypatch.setattr(settings_module.time, "tzset", lambda: calls.append(os.environ["TZ"]), raising=False)
    monkeypatch.setattr(settings_module, "ZoneInfo", lambda name: name)  # Windows não tem a base de fusos
    monkeypatch.setenv("TZ", "UTC")
    assert settings_module.apply_timezone("America/Belem") is True
    assert calls == ["America/Belem"]


def test_invalid_timezone_keeps_system_clock(monkeypatch):
    def missing(name):
        raise settings_module.ZoneInfoNotFoundError(name)

    monkeypatch.setattr(settings_module.time, "tzset", lambda: pytest.fail("não deveria trocar o fuso"), raising=False)
    monkeypatch.setattr(settings_module, "ZoneInfo", missing)
    assert settings_module.apply_timezone("Marte/Olimpo") is False
    assert settings_module.apply_timezone("") is False
