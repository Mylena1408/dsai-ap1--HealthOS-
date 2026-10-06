# Decisões arquiteturais (ADRs)

Registro curto das decisões tomadas durante a expansão didática do HealthOS.
Cada decisão traz o contexto, o que foi decidido e as consequências.

---

## ADR-001 — Expandir de forma incremental, sem reescrever

**Contexto.** O HealthOS já tinha 30 endpoints, um portal web e regras de negócio
no domínio (imutabilidade de notas, conflito de agenda, coparticipação etc.).

**Decisão.** Toda evolução acontece por extensão: novos módulos, novas tabelas e
novas rotas. Endpoints existentes mantêm caminho e formato de resposta. A suíte
`tests/api/test_existing_endpoints.py` trava esse comportamento.

**Consequências.** Antes de cada commit, a regressão precisa estar verde.

---

## ADR-002 — Sem autenticação; perfis apenas simulados

**Contexto.** O sistema é acadêmico e demonstrativo. O `PermissionChecker` já
estava em modo de bypass para a demonstração pública.

**Decisão.** Não criar senhas, JWT, OAuth nem recuperação de conta. Papéis
(paciente, médico, farmacêutico, administrador) são escolhidos na interface só
para demonstrar fluxos. O endpoint legado `POST /api/v1/auth/login` permanece
como estava, para não quebrar compatibilidade, mas não é usado pelo portal.

**Consequências.** Nenhum dado real deve ser cadastrado; todos os geradores
usam dados fictícios (CPFs sintéticos, e-mails `@example.com`).

---

## ADR-003 — Somente tabelas novas (sem migrações destrutivas)

**Contexto.** As tabelas são criadas por `Base.metadata.create_all` no startup.
Esse mecanismo cria tabelas ausentes, mas **não** adiciona colunas a tabelas
existentes. O banco de produção (Render) não é controlado pelo projeto.

**Decisão.** Novos dados de entidades existentes vão para tabelas novas
relacionadas (ex.: perfil estendido do paciente em tabela 1:1), nunca para
`ALTER TABLE` em tabelas existentes. Nenhum `DROP` é executado.

**Consequências.** A aplicação continua funcionando em bancos já existentes sem
passos manuais. Se o projeto passar a usar PostgreSQL gerenciado, o Alembic
pode ser introduzido com uma revisão base equivalente ao estado atual.

---

## ADR-004 — Frontend em JavaScript modular, sem etapa de build

**Contexto.** O portal era um único `index.html` com script inline e Tailwind
via CDN. Introduzir React/Vite exigiria Node e build no deploy.

**Decisão.** Manter HTML + JavaScript puro, organizado em módulos ES:

```
static/
├── css/app.css            estilos compartilhados
├── js/core/api.js         cliente HTTP único (tratamento de erros da API)
├── js/core/dom.js         escapeHtml, formatadores, toast, estados vazios
├── js/core/layout.js      navegação e faixa de "ambiente didático"
├── js/pages/<pagina>.js   lógica de cada página
└── pages/<pagina>.html    páginas servidas em /app/<pagina>
```

Handlers inline (`onclick`) foram trocados por atributos `data-*` com delegação
de eventos. Todo dado da API que entra em `innerHTML` passa por `escapeHtml`.

**Consequências.** O deploy continua idêntico (FastAPI serve `/static`).

---

## ADR-005 — Observabilidade simples e em memória

**Decisão.** `/health` (liveness), `/status` (versão, uptime, conexão e contagens
do banco) e `/metrics` (requisições por rota, latência e erros). As métricas
usam o *padrão* da rota (`/patients/{patient_id}`) para não criar uma série por
UUID, e são zeradas a cada reinício.

**Consequências.** Sem dependências novas; suficiente para fins didáticos. Em um
sistema real, o caminho natural seria Prometheus/OpenTelemetry.

---

## ADR-006 — Consultas em tabelas próprias, sem alterar a agenda legada

**Contexto.** A tabela `schedules` guarda horários livres que o portal reserva
(`AVAILABLE → BOOKED`). Ela referencia `users.id` como médico e não comporta
especialidade, tipo de consulta, confirmação, atendimento nem histórico.

**Decisão.** O módulo de consultas usa tabelas novas (`appointments` e
`appointment_status_history`) e o cadastro novo de profissionais
(`professionals`, `professional_working_hours`, `departments`, `specialties`).
A disponibilidade é calculada a partir do expediente, sem pré-criar horários.
A agenda legada continua funcionando exatamente como antes, para o portal.

**Consequências.** Existem dois fluxos de agendamento durante a transição; a
documentação deixa claro qual é o legado. As regras de estado ficam na
entidade `Appointment` e são testadas sem banco; o relógio é injetado no caso
de uso para testar regras dependentes de horário.

---

## ADR-007 — Exceções de domínio tipadas para os módulos novos

**Decisão.** `EntityNotFoundError` (404), `BusinessRuleViolation` (400),
`ConflictError` e `InvalidTransitionError` (409), traduzidas por handlers
globais registrados em `app/presentation/api/error_handlers.py`. Os routers
novos não precisam de `try/except`. Os routers legados não foram alterados.

---

## ADR-008 — Timestamps gerados no Python nas tabelas novas

**Contexto.** Colunas com `server_default`/`onupdate=func.now()` ficam
*expiradas* após o flush; ler o valor depois exige I/O implícito, o que gera
`MissingGreenlet` em sessões assíncronas.

**Decisão.** Nas tabelas novas, `created_at`/`updated_at` usam
`default=datetime.now` / `onupdate=datetime.now` (valor conhecido pelo Python).
