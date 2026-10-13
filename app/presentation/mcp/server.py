"""Servidor Model Context Protocol (MCP) do HealthOS.

Expoe os casos de uso como *tools* MCP sem furar a Clean Architecture.

Uso stdio (clientes MCP como Claude Desktop / VS Code):
    pip install mcp   # apos incluir em requirements.txt
    python -m app.presentation.mcp.server
Uso HTTP p/ testes:
    python app/presentation/mcp/server.py streamable-http --port 8001
"""
from __future__ import annotations

import argparse
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, time
from typing import Annotated, Optional

from mcp.server.mcpserver import MCPServer as _ServerCls
from mcp.server.mcpserver.exceptions import ToolError

# Compat: SDK v1 chamava FastMCP (mcp.server.fastmcp); SDK v2 renomeou p/ MCPServer.
try:  # pragma: no cover - apenas p/ quem ainda usa SDK v1
    from mcp.server.fastmcp import FastMCP as _LegacyCls  # type: ignore

    _ServerCls = _LegacyCls  # noqa: F811
except ModuleNotFoundError:
    pass
from pydantic import Field

from app.application.dtos.appointment_dto import AppointmentCreateDTO
from app.application.interfaces.appointment_repository import AppointmentFilters
from app.application.interfaces.professional_repository import ProfessionalFilters
from app.application.use_cases.appointment_use_case import AppointmentUseCase
from app.application.use_cases.professional_use_case import ProfessionalUseCase
from app.domain.entities.appointment import AppointmentStatus, AppointmentType
from app.domain.exceptions.common import BusinessRuleViolation, ConflictError, EntityNotFoundError
from app.infrastructure.events import build_publisher
from app.infrastructure.persistence.database import AsyncSessionLocal
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import (
    SQLAlchemyAppointmentRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_patient_repository import (
    SQLAlchemyPatientRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyCatalogRepository,
    SQLAlchemyProfessionalRepository,
)

logger = logging.getLogger("healthos.mcp")
mcp = _ServerCls("HealthOS")


@asynccontextmanager
async def db_session():
    """Uma sessao por chamada de tool (equivale ao get_db do FastAPI)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _appointment_uc(session) -> AppointmentUseCase:
    return AppointmentUseCase(
        SQLAlchemyAppointmentRepository(session),
        SQLAlchemyProfessionalRepository(session),
        SQLAlchemyCatalogRepository(session),
        SQLAlchemyPatientRepository(session),
        events=build_publisher(session),
    )


def _professional_uc(session) -> ProfessionalUseCase:
    return ProfessionalUseCase(
        SQLAlchemyProfessionalRepository(session),
        SQLAlchemyCatalogRepository(session),
    )


def _parse_uuid(value: str, campo: str) -> uuid.UUID:
    try:
        return uuid.UUID(value.strip())
    except (ValueError, AttributeError):
        raise ToolError(f"'{campo}' deve ser UUID valido, recebido: {value!r}.")


def _parse_day(dia: str) -> date:
    try:
        return date.fromisoformat(dia.strip())
    except ValueError:
        raise ToolError(f"'dia' deve ser YYYY-MM-DD, recebido: {dia!r}.")


def _parse_datetime(value: str, campo: str) -> datetime:
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        raise ToolError(f"'{campo}' deve ser ISO-8601 (ex.: 2026-10-20T14:30:00), recebido: {value!r}.")


def _domain_error(op: str, exc: Exception) -> ToolError:
    if isinstance(exc, ToolError):
        return exc
    if isinstance(exc, EntityNotFoundError):
        return ToolError(f"{op}: nao encontrado - {exc}.")
    if isinstance(exc, (BusinessRuleViolation, ConflictError)):
        return ToolError(f"{op}: regra de negocio - {exc}.")
    logger.exception("MCP %s falhou", op)
    return ToolError(f"{op}: erro interno - {exc}.")

@mcp.tool()
async def listar_consultas(
    professional_id: Annotated[str, Field(description="UUID do profissional")],
    dia: Annotated[str, Field(description="Dia YYYY-MM-DD")],
    limit: Annotated[int, Field(description="Maximo de itens", ge=1, le=200)] = 50,
    offset: Annotated[int, Field(description="Deslocamento", ge=0)] = 0,
) -> list[dict]:
    """Lista consultas de um profissional num dia (00:00-23:59). Equivale a GET /appointments."""
    prof_id = _parse_uuid(professional_id, "professional_id")
    day = _parse_day(dia)
    filters = AppointmentFilters(
        professional_id=prof_id,
        date_from=datetime.combine(day, time.min),
        date_to=datetime.combine(day, time.max),
        limit=limit, offset=offset,
    )
    try:
        async with db_session() as session:
            page = await _appointment_uc(session).search(filters)
        return [c.model_dump(mode="json") for c in page.items]
    except (ToolError, ValueError, EntityNotFoundError, BusinessRuleViolation, ConflictError) as e:
        raise _domain_error("listar_consultas", e)


@mcp.tool()
async def detalhar_consulta(
    appointment_id: Annotated[str, Field(description="UUID da consulta")],
) -> dict:
    """Retorna uma consulta com historico e transicoes permitidas."""
    aid = _parse_uuid(appointment_id, "appointment_id")
    try:
        async with db_session() as session:
            dto = await _appointment_uc(session).get(aid)
        return dto.model_dump(mode="json")
    except (ToolError, ValueError, EntityNotFoundError, BusinessRuleViolation, ConflictError) as e:
        raise _domain_error("detalhar_consulta", e)


@mcp.tool()
async def disponibilidade_profissional(
    professional_id: Annotated[str, Field(description="UUID do profissional")],
    data_inicio: Annotated[Optional[str], Field(description="Data inicial YYYY-MM-DD")] = None,
    dias: Annotated[int, Field(description="Janela 1-31", ge=1, le=31)] = 7,
    duracao_minutos: Annotated[Optional[int], Field(description="Duracao 10-240", ge=10, le=240)] = None,
) -> list[dict]:
    """Horarios livres = expediente menos consultas ativas menos passado."""
    prof_id = _parse_uuid(professional_id, "professional_id")
    start_day = _parse_day(data_inicio) if data_inicio else date.today()
    try:
        async with db_session() as session:
            slots = await _appointment_uc(session).available_slots(
                prof_id, datetime.combine(start_day, time.min), dias, duracao_minutos)
        return [s.model_dump(mode="json") for s in slots]
    except (ToolError, ValueError, EntityNotFoundError, BusinessRuleViolation, ConflictError) as e:
        raise _domain_error("disponibilidade_profissional", e)


@mcp.tool()
async def buscar_profissionais(
    busca: Annotated[Optional[str], Field(description="Trecho do nome ou registro")] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> dict:
    """Busca profissionais por nome/registro. Equivale a GET /professionals?q=..."""
    try:
        async with db_session() as session:
            page = await _professional_uc(session).search(
                ProfessionalFilters(query=busca, limit=limit, offset=offset))
        return page.model_dump(mode="json")
    except (ToolError, ValueError, EntityNotFoundError, BusinessRuleViolation, ConflictError) as e:
        raise _domain_error("buscar_profissionais", e)

@mcp.tool()
async def agendar_consulta(
    patient_id: Annotated[str, Field(description="UUID do paciente")],
    professional_id: Annotated[str, Field(description="UUID do profissional")],
    start_time: Annotated[str, Field(description="Inicio ISO-8601 ex.: 2026-10-20T14:30:00")],
    motivo: Annotated[Optional[str], Field(description="Motivo max 500", max_length=500)] = None,
    tipo: Annotated[str, Field(description="PRIMEIRA_CONSULTA|RETORNO|URGENCIA|TELECONSULTA")] = "PRIMEIRA_CONSULTA",
    duracao_minutos: Annotated[Optional[int], Field(description="10-240 mult 5", ge=10, le=240)] = None,
) -> dict:
    """Agenda consulta futura (valida paciente, expediente e conflitos)."""
    try:
        tipo_enum = AppointmentType(tipo.strip().upper())
    except ValueError:
        validos = ", ".join(t.value for t in AppointmentType)
        raise ToolError(f"'tipo' invalido: {tipo!r}. Use: {validos}.")
    dto = AppointmentCreateDTO(
        patient_id=_parse_uuid(patient_id, "patient_id"),
        professional_id=_parse_uuid(professional_id, "professional_id"),
        start_time=_parse_datetime(start_time, "start_time"),
        duration_minutes=duracao_minutos,
        appointment_type=tipo_enum, reason=motivo,
    )
    try:
        async with db_session() as session:
            created = await _appointment_uc(session).book(dto)
        return created.model_dump(mode="json")
    except (ToolError, ValueError, EntityNotFoundError, BusinessRuleViolation, ConflictError) as e:
        raise _domain_error("agendar_consulta", e)


@mcp.tool()
async def gerenciar_consulta(
    appointment_id: Annotated[str, Field(description="UUID da consulta")],
    acao: Annotated[str, Field(description="confirmar|iniciar|concluir|faltou|remarcar|cancelar")],
    motivo: Annotated[Optional[str], Field(description="Obrigatorio p/ cancelar; nota p/ concluir")] = None,
    novo_horario: Annotated[Optional[str], Field(description="Novo inicio ISO-8601 p/ remarcar")] = None,
) -> dict:
    """Aplica transicao: AGENDADA->CONFIRMADA->EM_ANDAMENTO->FINALIZADA."""
    aid = _parse_uuid(appointment_id, "appointment_id")
    action = acao.strip().lower()
    try:
        async with db_session() as session:
            uc = _appointment_uc(session)
            if action == "confirmar":
                out = await uc.confirm(aid)
            elif action == "iniciar":
                out = await uc.start(aid)
            elif action == "concluir":
                out = await uc.complete(aid, motivo)
            elif action == "faltou":
                out = await uc.mark_no_show(aid)
            elif action == "cancelar":
                if not motivo or len(motivo.strip()) < 3:
                    raise ToolError("Para cancelar informe 'motivo' com 3+ caracteres.")
                out = await uc.cancel(aid, motivo.strip())
            elif action == "remarcar":
                if not novo_horario:
                    raise ToolError("Para remarcar informe 'novo_horario' ISO-8601.")
                out = await uc.reschedule(aid, _parse_datetime(novo_horario, "novo_horario"))
            else:
                raise ToolError(f"Acao {acao!r} invalida.")
        return out.model_dump(mode="json")
    except (ToolError, ValueError, EntityNotFoundError, BusinessRuleViolation, ConflictError) as e:
        raise _domain_error("gerenciar_consulta", e)

@mcp.tool()
async def buscar_consultas_paciente(
    patient_id: Annotated[str, Field(description="UUID do paciente")],
    status: Annotated[Optional[str], Field(description="Ex.: AGENDADA (vazio=todas)")] = None,
    limit: Annotated[int, Field(ge=1, le=200)] = 20,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> dict:
    """Lista consultas de um paciente, opcionalmente por situacao."""
    pid = _parse_uuid(patient_id, "patient_id")
    statuses: list[AppointmentStatus] = []
    if status:
        try:
            statuses = [AppointmentStatus(status.strip().upper())]
        except ValueError:
            validos = ", ".join(s.value for s in AppointmentStatus)
            raise ToolError(f"'status' invalido: {status!r}. Use: {validos}.")
    try:
        async with db_session() as session:
            page = await _appointment_uc(session).search(
                AppointmentFilters(patient_id=pid, statuses=statuses, limit=limit, offset=offset))
        return page.model_dump(mode="json")
    except (ToolError, ValueError, EntityNotFoundError, BusinessRuleViolation, ConflictError) as e:
        raise _domain_error("buscar_consultas_paciente", e)


@mcp.resource("healthos://info")
def healthos_info() -> str:
    """Contexto estatico do dominio para o LLM."""
    return (
        "HealthOS - gestao hospitalar (Clean Architecture). "
        "Consulta: AGENDADA->CONFIRMADA->EM_ANDAMENTO->FINALIZADA; "
        "finais: CANCELADA (so antes), NAO_COMPARECEU (so depois). "
        "IDs sao UUIDs. Tools: listar_consultas, detalhar_consulta, "
        "disponibilidade_profissional, buscar_profissionais, "
        "buscar_consultas_paciente, agendar_consulta, gerenciar_consulta."
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Servidor MCP do HealthOS")
    p.add_argument("transport", nargs="?", default="stdio",
                   choices=["stdio", "sse", "streamable-http"])
    p.add_argument("--port", type=int, default=8001)
    p.add_argument("--host", default="127.0.0.1")
    return p


def main(argv: Optional[list[str]] = None) -> None:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
 