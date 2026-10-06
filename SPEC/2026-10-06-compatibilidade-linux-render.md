# Compatibilidade Linux e Render (2026-10-06)

## O quê e por quê

O projeto é desenvolvido no Windows e publicado no Render, que roda Linux. O `requirements.txt` original era uma cópia do Python global do Windows e quebrou o deploy; depois, sem versões, o Render passou a instalar pacotes diferentes dos testados e, com Python 3.14, até versões sem pacote disponível (ADR-026).

Além disso, os horários da aplicação são gravados sem fuso e comparados com o relógio do processo, mas o servidor Linux roda em UTC. Esta parte fixa o ambiente, configura o fuso e aceita a URL de PostgreSQL do Render sem ajuste manual.

## Modelo de dados (resumo)

Sem tabelas novas. Configuração:

- **Python:** `3.13` em `.python-version`. O `Dockerfile` usa `python:3.13-slim`.
- **`requirements.txt`:** versões exatas, diretas e transitivas (ex.: `fastapi==0.115.0`, `SQLAlchemy==2.0.32`, `asyncpg==0.31.0`, `aiosqlite==0.22.1`, `fpdf2==2.8.9`, `pydantic-core==2.20.1`).
- **`requirements-dev.txt`:** inclui `-r requirements.txt` e as versões exatas de teste (`pytest==9.1.1`, `pytest-asyncio==1.4.0`, `httpx==0.27.2`, entre outras).
- **Variável nova `APP_TIMEZONE`** (`config/settings.py`): padrão `America/Belem`.
- **Variáveis no `render.yaml`:** `DATABASE_URL` (`sync: false`, fica só no painel), `SECRET_KEY` (`generateValue: true`), `SEED_DEMO_DATA` (`"False"`), `APP_TIMEZONE` (`America/Belem`), `ALERT_EVALUATION_INTERVAL_MINUTES` (`"15"`), `AI_PROVIDER` (`demo`).
- **`.env.example`:** modelo com `DATABASE_URL=sqlite:///./app.db`, `SECRET_KEY`, `SEED_DEMO_DATA`, `ALERT_EVALUATION_INTERVAL_MINUTES`, `APP_TIMEZONE`, `AI_PROVIDER`, `AI_MODEL` e as demais chaves do login legado.

## Rotas (`/api/v1`)

Sem rotas novas. Arquivos e comandos que esta parte define:

- `render.yaml`: serviço `web`, `runtime: python`, `plan: free`, `buildCommand: pip install -r requirements.txt`, `startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT`, `healthCheckPath: /health`.
- `Dockerfile`: instala `tzdata`, as dependências de `requirements.txt` e roda `uvicorn main:app --host 0.0.0.0 --port ${PORT}` (`PORT=8000`).
- Testes: `pip install -r requirements-dev.txt`.

## Critérios de aceitação

### Versões
- O Python fica em 3.13. Se `PYTHON_VERSION` existir no painel do Render, ela tem prioridade e deve ficar em 3.13.x.
- Todas as dependências de execução e de teste têm versão exata (`==`).
- `render.yaml` e `Dockerfile` usam o mesmo comando de start.

### Banco de dados (`async_database_url`)
- `sqlite://...` vira `sqlite+aiosqlite://...`.
- `postgres://...` e `postgresql://...` viram `postgresql+asyncpg://...`.
- Em URLs `postgresql+asyncpg://`, `sslmode=` vira `ssl=`.
- URLs que já indicam o driver (`sqlite+aiosqlite://`, `postgresql+asyncpg://`) são mantidas.
- A produção usa PostgreSQL: a URL fica só no painel e o Blueprint não a altera.

### Fuso horário (`apply_timezone`)
- Em Linux/macOS, define `TZ` e chama `time.tzset()`; devolve `True`.
- No Windows (sem `time.tzset`), não faz nada e devolve `False`: vale o fuso da máquina.
- Nome IANA (com `/`) que não existe no sistema não muda o fuso, registra um aviso e devolve `False`.
- Valor vazio devolve `False`.
- A forma POSIX (ex.: `<-03>3`) é aplicada sem consultar a base de fusos.
- O fuso é aplicado ao carregar `config/settings.py`.

### Segredos
- `.env` não é versionado; `.env.example` serve de modelo.
- `ANTHROPIC_API_KEY` não aparece em `render.yaml` nem em `.env.example` com valor.

## Testes esperados

- Unidade: `tests/unit/test_platform_config.py` (conversão das URLs para drivers assíncronos, inclusive `sslmode`; fuso ignorado sem `tzset`; fuso aplicado em Unix; fuso inválido mantém o relógio; forma POSIX sem base de fusos).

## Fora do escopo

- Python 3.14 (sem pacotes para as versões fixadas).
- Teste da imagem Docker (o ADR-026 registra que não foi executada).
- Scripts específicos de Windows (`.bat`, PowerShell).
