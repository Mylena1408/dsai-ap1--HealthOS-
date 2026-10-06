from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

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

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
