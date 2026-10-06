"""Porta para provedores de IA. A aplicação depende só desta interface (ADR-021)."""
from abc import ABC, abstractmethod
from typing import Optional

from app.domain.entities.assistant import AIResponse, ChatMessage, PatientContext


class AIService(ABC):
    provider: str
    model: str

    @abstractmethod
    async def summarize_record(self, context: PatientContext) -> AIResponse: ...

    @abstractmethod
    async def analyze_exam(self, context: PatientContext, exam_description: str) -> AIResponse:
        """`exam_description`: nome do exame e resultados com faixas e classificação."""

    @abstractmethod
    async def analyze_symptoms(self, description: str, context: Optional[PatientContext]) -> AIResponse: ...

    @abstractmethod
    async def generate_insights(self, context: PatientContext) -> AIResponse: ...

    @abstractmethod
    async def answer_question(self, question: str, context: Optional[PatientContext],
                              history: list[ChatMessage]) -> AIResponse: ...


class AIUnavailableError(Exception):
    """O provedor configurado não pôde responder (credencial ausente, SDK não instalado, rede)."""
