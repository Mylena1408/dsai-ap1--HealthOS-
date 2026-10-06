from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config.settings import settings


def async_database_url(url: str) -> str:
    """Ajusta a URL para o driver assíncrono usado pela aplicação (AsyncSession).

    - sqlite://...                     -> sqlite+aiosqlite://...
    - postgres:// ou postgresql://...  -> postgresql+asyncpg://... (formato fornecido pelo Render/Heroku)
    - ?sslmode=require                 -> ?ssl=require (o asyncpg não aceita "sslmode")
    URLs que já indicam o driver são mantidas.
    """
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("sslmode=", "ssl=")
    return url


DATABASE_URL = async_database_url(settings.DATABASE_URL)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    """Dependência do FastAPI para fornecer sessões de banco de dados."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
