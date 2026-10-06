# Observabilidade, frontend modular e dados de demonstração (2026-10-06)

## O quê e por quê

Sem um ponto de verificação, não dá para saber se a aplicação e o banco estão de pé no Render, nem quais rotas falham ou demoram. Esta parte cria `/health`, `/status` e `/metrics`, com um middleware que registra cada requisição.

O portal era um único HTML com script embutido e `onclick`. Ele passa a usar módulos ES compartilhados e páginas próprias em `/app/{page}`. Para demonstrar o sistema sem cadastrar tudo à mão, há um gerador determinístico e idempotente de dados fictícios.

## Modelo de dados (resumo)

Não há tabelas novas nesta parte. As métricas vivem em memória (`MetricsRegistry`) e são zeradas a cada reinício.

- **Resposta de `/status`:** `status` (`ok` ou `degraded`), `version`, `python`, `uptime_seconds` e `database` com `dialect`, `status` (`ok` ou `error`), `latency_ms`, `records` (ou `error` com o nome da exceção).
- **Contagens em `database.records`:** `patients`, `users`, `professionals`, `appointments`, `schedules`, `medications`, `invoices`. Apenas números, nenhum dado pessoal.
- **Resposta de `/metrics`:** `uptime_seconds`, `requests_total`, `errors_total`, `error_rate` e `routes`.
- **Cada rota em `routes`** (chave `"<MÉTODO> <padrão da rota>"`): `count`, `errors`, `avg_ms`, `max_ms`, `status_codes` (código como texto).
- **Configuração:** `SEED_DEMO_DATA` (booleano, padrão `False`, em `config/settings.py` e `.env.example`).

## Rotas

Fora de `/api/v1`, para facilitar health checks do Render:

- `GET /health`
- `GET /status`
- `GET /metrics`

Interface:

- `GET /` (portal, `index.html`)
- `GET /app/{page}` (serve `static/pages/{page}.html`; fora do schema OpenAPI)
- `/static/...` (CSS e módulos JavaScript)

## Critérios de aceitação

### Health e status
- `GET /health` responde `{"status": "ok"}`.
- `GET /status` executa `SELECT 1` no banco e informa o dialeto e a latência em ms.
- Com o banco acessível, `status` e `database.status` são `ok` e `database.records` traz as contagens.
- Se o banco falhar, a resposta é 503, `status` é `degraded`, `database.status` é `error` e `database.error` traz o nome da exceção. A falha não é propagada.
- `version` reflete `APP_VERSION` do `system_router.py`.

### Métricas
- Toda requisição é registrada com método, padrão da rota, código HTTP e duração.
- A chave usa o padrão da rota (ex.: `GET /api/v1/admin/patients/{patient_id}`), nunca o UUID literal.
- Requisição sem rota correspondente é agrupada como `<não roteado>`.
- Caminhos iniciados por `/static`, `/metrics` e `/favicon.ico` não entram nas métricas.
- Só códigos maiores ou iguais a 500 contam como erro.
- `avg_ms` é a média das durações; `error_rate` é `errors_total / requests_total`, arredondado a 4 casas, e vale 0 sem requisições.
- Cada requisição também é registrada no log `healthos.http`; respostas 5xx saem como aviso.

### Frontend modular
- O portal (`/`) não usa `onclick=` e carrega `/static/js/pages/portal.js` como módulo.
- `static/js/core/api.js` concentra as chamadas HTTP. Erros de validação do FastAPI viram mensagem legível por campo. Falha de rede mostra mensagem de conexão.
- `static/js/core/dom.js` oferece `escapeHtml`. Todo dado da API passa por ele antes de entrar em `innerHTML`.
- `static/js/core/layout.js` monta a navegação compartilhada (menus "Atendimento" e "Gestão", busca com atalho `/`) e a faixa que avisa que o ambiente é didático e os dados são fictícios.
- `static/js/core/labels.js` traduz os valores enumerados da API para rótulos em português.
- `GET /app/{page}` aceita só nomes no padrão `^[a-z][a-z0-9-]*$`. Nome fora do padrão retorna 422.
- Página inexistente retorna 404 com "Página não encontrada.".
- `/app/status` consome `/status` e `/metrics` e mostra o estado do banco, as contagens e as rotas.
- Os arquivos `.js` em `/static` são servidos com tipo JavaScript.

### Dados de demonstração
- `python -m scripts.seed_demo` popula o banco de `DATABASE_URL`. Parâmetros: `--patients` (padrão 50), `--appointments` (padrão 100), `--exams` (padrão 200) e `--seed` (padrão 2026).
- Com `SEED_DEMO_DATA=True`, o seed roda no startup. Um erro no seed é registrado no log e não impede a aplicação de subir.
- Mesma semente gera os mesmos dados. Uma segunda execução não duplica pacientes, medicamentos, profissionais, consultas, prontuários, sinais vitais, exames, prescrições nem lotes.
- O seed usa os casos de uso, então as regras de domínio continuam valendo.
- Os CPFs gerados têm dígitos verificadores válidos. Os e-mails usam o domínio `example.com`.
- Os medicamentos fictícios recebem estoque em `FARMACIA_CENTRAL`, `ALA_A` e `PRONTO_ATENDIMENTO`. Algumas quantidades ficam abaixo do mínimo, então o relatório de estoque crítico não fica vazio.
- São criados 20 profissionais. As consultas passadas terminam como finalizada, não compareceu ou cancelada; as futuras ficam agendada, confirmada ou cancelada. Consultas ativas não se sobrepõem para o mesmo profissional nem para o mesmo paciente.
- O histórico de cada consulta e de cada exame é cronológico e termina no status atual.
- A soma dos lotes nunca passa do total legado do mesmo medicamento e local.
- Ao final, o motor de alertas é avaliado sobre os dados gerados.

## Testes esperados

- Unidade: `tests/unit/test_observability_and_seed_data.py` (agregação de métricas por rota, CPF sintético válido, pacientes fictícios determinísticos).
- Integração: `tests/integration/test_demo_seed.py` (idempotência, estoque crítico, profissionais e consultas coerentes, prontuários, sinais vitais e exames, lotes da farmácia).
- API: `tests/api/test_system_endpoints.py` (`/health`, `/status`, métricas por padrão de rota, `/app/status`, `/app/inexistente`, portal sem `onclick`).
- Frontend: `tests/frontend/components.test.mjs` (`npm test`, inclui `escapeHtml`), `tests/frontend/pages.smoke.mjs` (`npm run smoke`, páginas contra a API com dados de demonstração) e `tests/frontend/a11y.review.mjs` (`npm run a11y`, axe WCAG 2.1 AA em navegador real).

## Fora do escopo

- Prometheus, OpenTelemetry ou qualquer armazenamento persistente de métricas.
- Proteção de `/status` e `/metrics` por autenticação.
- Build ou empacotamento do frontend (os módulos são servidos como estão).
- Dados reais ou importação de bases externas.
