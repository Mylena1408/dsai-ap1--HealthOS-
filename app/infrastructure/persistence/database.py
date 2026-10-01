from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

# A URL de banco de dados padrão para desenvolvimento local.
# Em produção, ela será substituída pela variável de ambiente DATABASE_URL.
DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/healthos"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    """Dependência do FastAPI para fornecer sessões de banco de dados."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
