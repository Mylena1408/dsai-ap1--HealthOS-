"""Fixtures compartilhadas pelos testes.

O banco é configurado ANTES de importar a aplicação, porque config.settings e o
engine global são criados no momento do import. Assim os testes nunca tocam no
app.db usado na demonstração.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TEST_DB_DIR = tempfile.mkdtemp(prefix="healthos-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + Path(_TEST_DB_DIR, "api.db").as_posix()
os.environ.setdefault("SECRET_KEY", "test-only-secret")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.persistence.models.user_model import Base
import main  # noqa: F401 - registra todos os modelos no metadata


@pytest.fixture
async def db_session():
    """Sessão em um banco SQLite em memória, recriado a cada teste."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture(scope="session")
def client():
    """Cliente HTTP da aplicação completa (executa o startup com dados de demonstração)."""
    from fastapi.testclient import TestClient

    with TestClient(main.app) as test_client:
        yield test_client
