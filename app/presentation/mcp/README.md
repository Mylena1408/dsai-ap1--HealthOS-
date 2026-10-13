# MCP do HealthOS

Servidor [Model Context Protocol](https://modelcontextprotocol.io) que expoe
os casos de uso como *tools* para assistentes (Claude Desktop, VS Code, Inspector).

## Arquivos

| Arquivo | Papel |
|---|---|
| `app/presentation/mcp/server.py` | Servidor (7 tools + 1 resource + CLI stdio/sse/streamable-http) |
| `app/presentation/mcp/__init__.py` | Exporta `mcp` |
| `requirements.txt` | Pino `mcp==2.3.0` (SDK v2: `MCPServer`; v1 chamava `FastMCP`) |

## Tools

| Tool | Equivale a | Assinatura |
|---|---|---|
| `listar_consultas` | `GET /appointments?professional_id=&date_from=&date_to=` | `(professional_id: UUID, dia: YYYY-MM-DD, limit=50, offset=0) -> list` |
| `detalhar_consulta` | `GET /appointments/{id}` | `(appointment_id: UUID) -> dict` |
| `disponibilidade_profissional` | `GET /professionals/{id}/availability` | `(professional_id, data_inicio?, dias=7, duracao_minutos?) -> list` |
| `buscar_profissionais` | `GET /professionals?q=` | `(busca?, limit=20, offset=0) -> Page` |
| `buscar_consultas_paciente` | `GET /appointments?patient_id=&status=` | `(patient_id, status?, limit=20, offset=0) -> Page` |
| `agendar_consulta` | `POST /appointments` | `(patient_id, professional_id, start_time ISO-8601, motivo?, tipo?, duracao_minutos?) -> dict` |
| `gerenciar_consulta` | `POST /appointments/{id}/{confirm,start,complete,cancel,no-show,reschedule}` | `(appointment_id, acao, motivo?, novo_horario?) -> dict` |

Acoes de `gerenciar_consulta`: `confirmar | iniciar | concluir | faltou | remarcar | cancelar`
(maquina: `AGENDADA→CONFIRMADA→EM_ANDAMENTO→FINALIZADA`; finais `CANCELADA`, `NAO_COMPARECEU`).

Resource `healthos://info`: resumo do dominio para dar contexto ao LLM.

## Rodar

```bash
pip install -r requirements.txt
python -m app.presentation.mcp.server                    # stdio (clientes MCP)
python app/presentation/mcp/server.py streamable-http --port 8001   # HTTP p/ testes
```

## Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "healthos": {
      "command": "/home/carlos/Documentos/GitHub/dsai-ap1--HealthOS-/.venv/bin/python",
      "args": ["-m", "app.presentation.mcp.server"],
      "cwd": "/home/carlos/Documentos/GitHub/dsai-ap1--HealthOS-"
    }
  }
}
```

## Erros corrigidos do rascunho inicial

1. `build_list_appointments_use_case()` nao existia → injecao real via
   `AsyncSessionLocal` + repositorios SQLAlchemy + `build_publisher` (mesmo padrao dos routers).
2. `medico_id: int` → IDs do dominio sao `uuid.UUID`; parse na borda com `ToolError` legivel.
3. `date.fromisoformat` sem try/except → `_parse_day` valida `YYYY-MM-DD`.
4. `use_case.execute(...)` nao existia → metodo correto `AppointmentUseCase.search(AppointmentFilters(...))`
   com `date_from`/`date_to` cobrindo o dia inteiro (o rascunho passava so a data).
5. `mcp.run()` sem transporte → CLI com `stdio` (padrao p/ clientes), `sse` e `streamable-http`.
6. `FastMCP` (SDK v1) → `MCPServer` (SDK v2, `mcp==2.3.0` instalado); shim compat mantido.
7. `ValueError` virava `UnexpectedToolError` generico → `ToolError` (cliente recebe `is_error=True`
   com a mensagem de dominio/validacao).
8. `c.model_dump()` sem `mode="json"` quebrava com `UUID`/`datetime` → `mode="json"` em todas as tools.
