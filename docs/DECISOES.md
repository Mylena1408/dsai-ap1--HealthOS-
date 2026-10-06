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

---

## ADR-009 — Linha do tempo agregada na leitura

**Contexto.** Os eventos clínicos vivem em tabelas de módulos diferentes (inclusive
legadas). Manter uma tabela de eventos exigiria gravar em dois lugares a cada mudança.

**Decisão.** A linha do tempo é montada na leitura: o repositório consulta só as
fontes pedidas, converte cada registro em `TimelineEvent` e o caso de uso ordena e
pagina em memória.

**Consequências.** Nenhuma escrita duplicada e nenhuma alteração em tabelas
legadas. O custo cresce com o volume de registros *de um paciente*, o que é
adequado ao escopo didático; com volumes grandes, a evolução natural seria uma
tabela de eventos alimentada pela auditoria (prevista em ciclo posterior).

---

## ADR-010 — Busca de pacientes em rota nova

**Decisão.** A busca paginada fica em `GET /api/v1/patients`, em vez de alterar
`GET /api/v1/admin/patients/` (que retorna uma lista simples, sem filtro). O
contrato legado permanece idêntico; as telas novas usam a rota nova.

---

## ADR-011 — Faixa de referência como conceito único de domínio

**Decisão.** `ReferenceRange` (limites plausíveis, normais e críticos + `classify()`) é usado
tanto por sinais vitais quanto por analitos de exames. A classificação (`ResultFlag`) é a
mesma em todo o sistema, o que permite que alertas e indicadores futuros tratem os dois
módulos de forma uniforme.

---

## ADR-012 — Catálogo de exames como dado de referência; resultados com cópia da referência

**Decisão.** O catálogo é garantido no startup (idempotente, por código), independentemente
dos dados de demonstração. Ao registrar um resultado, unidade e texto da referência são
copiados para `exam_results`, de modo que laudos antigos não mudem se o catálogo mudar.

---

## ADR-013 — Gráficos em SVG próprio, sem biblioteca

**Contexto.** O frontend não tem etapa de build (ADR-004) e os gráficos são séries temporais
simples (uma métrica por gráfico).

**Decisão.** Componente `static/js/components/line-chart.js` em SVG puro: um eixo por gráfico
(nunca eixo duplo), linha de 2px, pontos com anel, faixa de referência recessiva, rótulo
direto só no último ponto, legenda apenas com 2+ séries, tooltip com cruz de leitura também
via teclado. Paleta validada (azul `#2a78d6` / laranja `#eb6834`: CVD ΔE 24,7, contraste ≥ 3:1).
Classificações sempre com **ícone + texto**, nunca só cor. A tabela de histórico é a visão
tabular equivalente aos gráficos.

---

## ADR-014 — Lotes como detalhe do estoque legado, com reconciliação

**Contexto.** `inventory_items` guarda um total por medicamento e local, alterado pelos
endpoints legados (`/pharmacy/inventory`, `/pharmacy/dispense`), sem lote nem validade por lote.

**Decisão.** O total legado continua sendo a fonte da verdade. Lotes (`stock_lots`) detalham parte
desse total; a diferença é "estoque sem lote". Toda operação do módulo novo começa reconciliando:
se a soma dos lotes passar do total (porque houve saída legada), o excesso é baixado dos lotes por
FEFO e registrado como movimentação `AJUSTE`. Saídas novas usam FEFO e nunca lotes vencidos.

**Consequências.** Os endpoints e o formato legado não mudam; o estoque nunca fica inconsistente;
a trilha de movimentações explica cada diferença. Custo: saídas legadas só se refletem nos lotes
na próxima operação nova (documentado e coberto por teste).

---

## ADR-015 — Regras de segurança clínica didáticas na prescrição

**Decisão.** Papéis verificados pelo tipo do profissional (médico prescreve, farmacêutico
dispensa — sem autenticação, conforme ADR-002); bloqueio por alergia ativa com correspondência
textual simples e possibilidade de prosseguir mediante justificativa registrada; limite para
substâncias controladas; validade de 30 dias. As regras são deliberadamente simples e
documentadas como didáticas — não substituem um sistema real de apoio à decisão.

---

## ADR-016 — Eventos de domínio com publicador em processo

**Contexto.** Auditoria e notificações precisam reagir a operações de vários módulos.
Chamar esses serviços dentro de cada caso de uso acoplaria todos os módulos entre si.

**Decisão.** Os casos de uso publicam `DomainEvent`s em um `EventPublisher` injetado (padrão
`NullPublisher`, o que mantém os testes de unidade e o código legado intactos). Em cada requisição,
o publicador entrega os eventos, de forma síncrona, à trilha de auditoria e à política de
notificações, usando a **mesma sessão** — se a operação falhar, nada é gravado; se um manipulador
falhar, a operação é desfeita. Não há fila/broker: não há volume nem requisito que justifique.

**Consequências.** Novos interessados (ex.: indicadores) entram registrando um manipulador.
Eventos não são reprocessáveis — aceitável no escopo didático.

---

## ADR-017 — Auditoria e caixa de notificações em tabelas novas

**Contexto.** O `AuditInterceptor` legado nunca foi ativado e, se fosse, falharia: grava um
`user_id` aleatório em `audit_logs.user_id`, que tem chave estrangeira obrigatória para `users`.
A tabela legada `notifications` mistura valores de status (`READ` e `LIDA`) e não tem "arquivada".

**Decisão.** `audit_events` e `inbox_notifications` são novas; o legado não é alterado (as rotas
`/notifications/...` continuam funcionando como antes) e fica documentado como tal.

---

## ADR-018 — Alertas por regra com deduplicação e resolução automática

**Decisão.** Regras declaradas na aplicação (`alert_rules.py`) e consultas no detector de
infraestrutura. Cada condição tem `dedup_key`; reavaliações atualizam, agravam ou resolvem
automaticamente. A avaliação periódica usa uma tarefa asyncio no próprio processo — em várias
instâncias, ela deveria virar um job externo para não executar em duplicidade.

---

## ADR-019 — Health Score como função pura e painéis por composição

**Decisão.** O Health Score é uma função de domínio sem I/O, que recebe fatos agregados e devolve
componentes explicados; componentes sem dados são "não aplicáveis" (não puxam a média para baixo).
É apresentado sempre como **indicador demonstrativo de acompanhamento**. Os painéis compõem os
casos de uso existentes (consultas, laboratório, farmácia, alertas) e usam um repositório de
agregações apenas para contagens e séries; os agrupamentos por dia/mês são feitos em Python para
funcionar igual em SQLite e PostgreSQL.

**Gráficos.** Paleta de três séries validada (azul, laranja, verde-água; CVD ΔE ≥ 9,2 entre todos os
pares). O verde-água tem contraste 2,8:1, abaixo de 3:1 — por isso o gráfico diário traz rótulos
diretos e uma visão em tabela. Medidores usam a cor de status sempre acompanhada de ícone e texto.

---

## ADR-020 — Testes de frontend em DOM simulado

**Contexto.** As páginas eram verificadas apenas por análise estática.

**Decisão.** `tests/frontend` usa `jsdom` (dependência só de desenvolvimento, fora do deploy):
`npm test` testa os componentes de gráfico sem servidor; `npm run smoke` executa todas as páginas,
as abas do prontuário e as visões do painel contra a API real e falha em qualquer erro de execução.
`static/js/package.json` marca os scripts como módulos ES para o Node; o navegador o ignora.

**Limite.** O DOM simulado não calcula layout: não detecta sobreposição visual, cortes de texto ou
problemas de responsividade — isso ainda exige olhar a página em um navegador.

---

## ADR-021 — Camada de IA desacoplada, com modo demonstração

**Contexto.** O assistente precisa funcionar em sala de aula sem chave de API e sem rede, e não
pode transformar o sistema em ferramenta de diagnóstico.

**Decisão.** A aplicação depende da interface `AIService`; a fábrica escolhe a implementação por
`AI_PROVIDER`:
- `DemoAIService` (padrão): regras determinísticas sobre o contexto do paciente — mesmas entradas,
  mesma resposta, o que também torna os testes estáveis;
- `ClaudeAIService`: SDK oficial `anthropic` (dependência opcional em `requirements-ai.txt`,
  importada só quando usada), com prompt de sistema que proíbe diagnóstico e prescrição, recusa
  tratada como resposta educada e erros do SDK convertidos em `ServiceUnavailableError` (503).

**Contexto mínimo.** `PatientContextBuilder` monta o contexto a partir dos casos de uso existentes
e envia apenas primeiro nome, idade e fatos clínicos; nenhum identificador direto sai do sistema.

**Segurança da resposta.** Sinais de alerta nos sintomas sempre geram orientação de urgência, em
qualquer provedor. Toda resposta carrega o aviso educacional. A auditoria registra o uso, não o
conteúdo. O histórico do chat fica em tabelas novas, somente por acréscimo.

**Consequência.** Trocar de provedor é configuração, não código; o modo demonstração não usa um
modelo de linguagem, e a interface deixa isso visível com o selo "Modo demonstração".

---

## ADR-022 — Financeiro ampliado em tabelas novas, com "em atraso" derivado

**Contexto.** O faturamento original não registrava pagamentos, não listava faturas e tinha um
status `ATRASADO` que nada aplicava. O banco de produção não pode receber `ALTER TABLE`.

**Decisão.**
- Pagamentos, cancelamentos, origem dos itens e preços ficam em tabelas novas que apenas
  referenciam `invoices`/`billing_items`. As rotas antigas continuam iguais e usam as mesmas regras.
- "Em atraso" é calculado a partir do vencimento na leitura (inclusive no filtro SQL), em vez de
  depender de um processo que atualize o status gravado.
- Para não faturar duas vezes, cada item guarda o atendimento de origem. A restrição "no máximo uma
  fatura não cancelada por atendimento" é verificada no caso de uso, e não por índice único,
  porque o cancelamento deve devolver o atendimento para faturamento sem apagar o histórico.
- Valores em `Decimal` com duas casas; a API serializa como texto ("15.00") para não perder precisão.

**Limite.** Não há estorno nem conciliação bancária: são conceitos fora do escopo didático.

---

## ADR-023 — Relatórios por catálogo, com formatação na infraestrutura

**Decisão.** Os relatórios seguem o mesmo desenho das regras de alerta: um catálogo na aplicação
(título, colunas com tipo, filtros aceitos) e uma fonte de dados na infraestrutura com uma consulta
por relatório. O caso de uso valida período, situação e limite de linhas e devolve uma tabela neutra;
CSV e PDF são apenas formas de apresentá-la. Acrescentar um relatório = uma entrada no catálogo e
um método na fonte (um teste garante que nenhum fica sem consulta).

**PDF com fpdf2.** Biblioteca em Python puro, sem dependências do sistema operacional, o que
mantém o deploy simples. As fontes padrão do PDF cobrem Latin-1; caracteres fora dela (travessão,
"≤") são trocados por equivalentes.

**Privacidade e rastreabilidade.** Os relatórios não incluem identificadores diretos (CPF, contato)
e toda exportação é auditada (o quê, em que formato, quantas linhas), não o conteúdo.

---

## ADR-024 — Busca global com consultas simples e resultados mínimos

**Decisão.** Uma consulta `LIKE` por tipo de entidade, limitada por grupo, em vez de um índice de
busca dedicado (FTS/Elasticsearch): o volume é pequeno e o comportamento fica igual em SQLite e
PostgreSQL. O termo é escapado (`%`, `_`) e sempre enviado como parâmetro.

**Privacidade.** Os resultados mostram só o necessário para reconhecer o registro; o CPF vai
mascarado. O link leva à página que já tem as regras de exibição completas.

**Limite.** No SQLite, `ILIKE` só ignora maiúsculas/minúsculas em letras sem acento ("álvaro" não
encontra "Álvaro"); no PostgreSQL a comparação é completa. Os relatórios, que estão em memória,
são comparados sem acentos.

---

## ADR-025 — Navegação agrupada e revisão em navegador real

**Contexto.** Com 16 páginas, a barra de links soltos não cabia: em telas largas metade dos itens
ficava escondida em uma rolagem horizontal pouco perceptível, e no celular os links desapareciam.
Os testes em DOM simulado não mediam layout, então nada disso aparecia nos testes.

**Decisão.**
- Navegação em três entradas: Painel e os grupos "Atendimento" e "Gestão" (padrão *disclosure* da
  WAI-ARIA: botão com `aria-expanded`, fecha com Esc, clique fora ou foco saindo). No celular, um
  botão de menu abre um painel com a busca e todas as páginas. O logo leva ao portal; notificações
  ficam no sino.
- `npm run a11y` (em `tests/frontend`) abre cada página no Edge/Chrome instalado (puppeteer-core,
  sem baixar navegador), em 1440, 1024, 768 e 375 px, e falha com rolagem horizontal, erro no
  console ou na tela, ou violação WCAG 2.1 AA apontada pelo axe-core. Também testa por teclado os
  menus, o seletor de paciente e o modal aberto.

**Correções que a revisão trouxe.** Seletor de paciente utilizável só com teclado (setas, Enter, Esc,
`aria-activedescendant`); gráficos com papéis ARIA válidos; textos e botões de fechar com contraste
mínimo de 4,5:1; rótulos de valor dos gráficos com espaço calculado pelo conteúdo; favicon.

**Limite.** A ferramenta automática encontra cerca de metade dos problemas de acessibilidade; leitura
com leitor de tela real (NVDA) continua recomendada.

---

## ADR-026 — Ambiente reproduzível entre Windows e Linux/Render

**Contexto.** O `requirements.txt` original era uma cópia do Python global do Windows (Anaconda,
Django, `pywin32`, `pywinpty`), que quebrou o deploy; depois foi reduzido a nomes sem versão. Com
isso o Render instalava sempre as versões mais novas — diferentes das testadas — e, como serviços
criados a partir de 2026-02 usam Python 3.14 por padrão, o build passou a depender de pacotes que
nem existem para as versões testadas (`pydantic-core 2.20.1` não tem pacote para 3.14). Além disso,
os horários da aplicação são locais e sem fuso, mas o Linux do Render roda em UTC.

**Decisão.**
- Python 3.12 em `.python-version` (único mecanismo; nada de `PYTHON_VERSION` no painel).
- `requirements.txt` com versões exatas, diretas e transitivas, conferidas em instalação limpa e
  com pacotes Linux (manylinux) baixados para 3.12 sem compilação.
- `APP_TIMEZONE` (padrão `America/Belem`) aplicado ao processo em Linux; no Windows vale o fuso
  da máquina.
- URLs `postgres://`/`postgresql://` convertidas para o driver assíncrono (asyncpg).
- `render.yaml` e `Dockerfile` documentam o mesmo comando de start
  (`uvicorn main:app --host 0.0.0.0 --port $PORT`).

**O que não precisou mudar.** Imports e nomes de arquivos já batiam em maiúsculas/minúsculas;
caminhos usam `os.path.join` a partir do próprio arquivo; não há scripts `.bat`/PowerShell, URLs de
`localhost` no frontend nem bibliotecas que dependam do Windows; leituras de arquivo de texto
indicam a codificação.

**Limite.** Esta máquina não tem Docker nem WSL: a execução em Linux real (imagem Docker e deploy
no Render) não foi feita aqui; a compatibilidade foi conferida pelos pacotes Linux e pela execução
em Windows com as mesmas versões.
