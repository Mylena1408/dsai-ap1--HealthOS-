"""Busca global por pacientes, profissionais, medicamentos, exames, faturas e relatórios."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.search_dto import SearchResultDTO
from app.application.use_cases.search_use_case import MAX_LENGTH, SearchUseCase
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.sqlalchemy_search_queries import SQLAlchemySearchQueries

router = APIRouter(tags=["Busca"])


async def get_search(session: AsyncSession = Depends(get_db)) -> SearchUseCase:
    return SearchUseCase(SQLAlchemySearchQueries(session))


@router.get("/search", response_model=SearchResultDTO, summary="Busca global (mínimo de 2 caracteres)")
async def search(q: str = Query(..., max_length=MAX_LENGTH, description="Nome, CPF, registro, código de amostra, nº de fatura..."),
                 per_group: int = Query(5, ge=1, le=20), use_case: SearchUseCase = Depends(get_search)):
    return await use_case.search(q, per_group)
