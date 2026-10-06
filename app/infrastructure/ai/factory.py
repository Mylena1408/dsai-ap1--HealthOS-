"""Escolhe o provedor de IA pela configuração (AI_PROVIDER) — ADR-021."""
from functools import lru_cache

from app.application.interfaces.ai_service import AIService
from app.infrastructure.ai.claude_provider import ClaudeAIService
from app.infrastructure.ai.demo_provider import DemoAIService
from config.settings import settings


@lru_cache
def get_ai_service() -> AIService:
    """Instância única por processo (o cliente HTTP do provedor real é reutilizado)."""
    if settings.AI_PROVIDER == "anthropic":
        return ClaudeAIService(model=settings.AI_MODEL)
    return DemoAIService()
