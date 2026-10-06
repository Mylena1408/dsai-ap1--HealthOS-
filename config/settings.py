import logging
import os
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DEBUG: bool = False
    # Quando verdadeiro, o startup popula o banco com dados fictícios (idempotente).
    SEED_DEMO_DATA: bool = False
    # Intervalo da avaliação automática de alertas (0 desliga; a rota /alerts/evaluate continua disponível).
    ALERT_EVALUATION_INTERVAL_MINUTES: int = 15
    # Assistente: "demo" (respostas determinísticas, sem rede) ou "anthropic" (requer requirements-ai.txt
    # e credenciais do SDK, ex.: ANTHROPIC_API_KEY).
    AI_PROVIDER: Literal["demo", "anthropic"] = "demo"
    AI_MODEL: str = "claude-opus-5-5"
    # Fuso dos horários do sistema (consultas, agendas, vencimentos). Os horários são gravados sem fuso
    # e comparados com o relógio do processo; servidores Linux (Render) rodam em UTC por padrão.
    APP_TIMEZONE: str = "America/Belem"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()


def apply_timezone(name: str) -> bool:
    """Faz `datetime.now()` seguir `name` em Linux/macOS. Devolve se o fuso foi aplicado.

    No Windows não há `time.tzset`: o processo usa o fuso configurado na própria máquina.
    """
    if not name or not hasattr(time, "tzset"):
        return False
    try:
        ZoneInfo(name)  # confere se o fuso existe no sistema antes de aplicá-lo
    except (ZoneInfoNotFoundError, ValueError):
        logging.getLogger("healthos.config").warning("APP_TIMEZONE inválido (%s); mantendo o fuso do sistema.", name)
        return False
    os.environ["TZ"] = name
    time.tzset()
    return True


apply_timezone(settings.APP_TIMEZONE)
