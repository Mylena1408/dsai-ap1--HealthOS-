# Servidor MCP com instalação opcional (2026-10-19)

## O quê e por quê

O commit `71857ac` acrescentou o servidor MCP (`app/presentation/mcp/`) e fixou `mcp==2.3.0` no `requirements.txt`. Esse pacote exige `pydantic>=2.12.0`, mas a API fixa `pydantic==2.8.2` (com FastAPI 0.115.0, Starlette 0.38.6 e pydantic-core fixados). O `pip install -r requirements.txt` fica impossível e o build no Render falha: a produção ficou na 1.13.0.

O servidor MCP é um programa à parte (`python -m app.presentation.mcp.server`); a API (`main.py`) não o importa. A correção torna a instalação dele opcional, como já é o provedor de IA real (`requirements-ai.txt`), sem apagar nada do código do MCP.

## Modelo de dados (resumo)

Sem mudanças.

## Rotas

Sem mudanças.

## Critérios de aceitação

- `requirements.txt` não contém `mcp`; `pip install --dry-run -r requirements.txt` resolve sem conflito.
- Novo `requirements-mcp.txt` com `mcp==2.3.0` e um aviso: exige `pydantic>=2.12`, acima do fixado para a API, então deve ser instalado num ambiente separado (outro venv) usado só pelo servidor MCP.
- `app/presentation/mcp/README.md` passa a indicar `requirements-mcp.txt` no lugar do `requirements.txt`.
- O código do MCP (`server.py`, `__init__.py`) não muda.
- A suíte de testes continua verde.

## Testes esperados

- `pip install --dry-run --ignore-installed -r requirements.txt` sem `ResolutionImpossible`.
- `pytest` completo verde.

## Fora do escopo

- Atualizar pydantic, FastAPI ou Starlette.
- Testes do servidor MCP.
