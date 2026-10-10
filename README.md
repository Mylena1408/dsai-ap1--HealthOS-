# HealthOS

Sistema de gerenciamento para serviços de saúde desenvolvido como atividade acadêmica.

## 🚀 Aplicação Online

Acesse a aplicação:

**[HealthOS — Aplicação Online](https://dsai-ap1-healthos.onrender.com/)**

## 📚 Documentação da API

A documentação interativa da API pode ser acessada pelo Swagger:

**[Swagger / OpenAPI](https://dsai-ap1-healthos.onrender.com/docs)**

## 🛠️ Tecnologias

* Python 3.12
* FastAPI
* SQLAlchemy 2 (assíncrono)
* SQLite (local) ou PostgreSQL (via `asyncpg`)
* Uvicorn
* Pydantic
* HTML + JavaScript (módulos ES) + Tailwind via CDN
* Render

> ⚠️ **Aplicação didática.** Todos os dados são fictícios, não há autenticação
> real e nada aqui substitui avaliação de um profissional de saúde.

## ▶️ Executando localmente

Requer **Python 3.13** (a mesma versão do Render, fixada em `.python-version`; 3.12 também passa nos testes).

**Windows (PowerShell)**

```powershell
py -3.13 -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload
```

**Linux / macOS**

```bash
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

**Docker** (Linux com Python 3.13 e o mesmo comando de start do Render)

```bash
docker build -t healthos .
docker run --rm -p 8000:8000 -e SECRET_KEY=dev -e SEED_DEMO_DATA=True healthos
```

Acesse `http://127.0.0.1:8000/` (portal), `/app/painel`, `/app/prontuario`, `/app/consultas`, `/app/laboratorio`, `/app/farmacia`, `/app/financeiro`, `/app/relatorios`, `/app/busca`, `/app/alertas`,
`/app/assistente`, `/app/notificacoes`, `/app/auditoria`, `/app/profissionais`, `/app/status` e `/docs` (Swagger).

### Variáveis de ambiente

| Variável | Obrigatória | Padrão / exemplo | Para quê |
|---|---|---|---|
| `DATABASE_URL` | sim | `sqlite:///./app.db` | Banco. `postgres://`/`postgresql://` também funcionam (driver asyncpg) |
| `SECRET_KEY` | sim | qualquer texto | Endpoint legado de login (demonstração) |
| `SEED_DEMO_DATA` | não | `False` | `True` cria os dados fictícios na inicialização (idempotente) |
| `APP_TIMEZONE` | não | `America/Belem` | Fuso dos horários; servidores Linux rodam em UTC. Alternativa sem base de fusos: `<-03>3` |
| `ALERT_EVALUATION_INTERVAL_MINUTES` | não | `15` | Avaliação automática de alertas (`0` desliga) |
| `AI_PROVIDER` | não | `demo` | `anthropic` usa o modelo real (requer `requirements-ai.txt` e `ANTHROPIC_API_KEY`) |
| `PORT` | só no Render/Docker | definida pela plataforma | Porta usada no comando de start |

### Deploy no Render

A configuração está em [`render.yaml`](render.yaml). Para o serviço já existente (criado pelo painel),
confira em **Settings**:

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Python:** 3.13 (`.python-version`). Se `PYTHON_VERSION` estiver definida no painel (hoje
  `3.13.4`), ela prevalece: mantenha-a em 3.13.x — o padrão atual do Render (3.14) não tem pacotes
  para as versões fixadas.
- **Environment:** `DATABASE_URL` (o PostgreSQL do Render), `SECRET_KEY`, `APP_TIMEZONE=America/Belem`
  e, para ter dados de demonstração, `SEED_DEMO_DATA=True` (idempotente: não duplica nem apaga nada).

A produção usa PostgreSQL, então os dados persistem entre deploys. As tabelas novas são criadas na
inicialização; as existentes não são alteradas.

### Dados de demonstração

```bash
python -m scripts.seed_demo                  # 50 pacientes, 20 profissionais, 100 consultas, 200 exames, 150 prescrições
python -m scripts.seed_demo --patients 120   # mais pacientes
```

O gerador é determinístico e idempotente: rodar de novo não duplica registros.
Para popular automaticamente no startup, defina `SEED_DEMO_DATA=True` no `.env`.
Ao final, as regras de alerta são avaliadas e geram alertas e notificações para os setores.

Não há login nem senha (ADR-002): o **perfil de demonstração** (canto superior direito) é um setor
(Recepção, Laboratório, Farmácia, Enfermagem, Coordenação clínica, Administração), um profissional
(com o tipo: médico, enfermeiro, farmacêutico...) ou um paciente. O perfil escolhe a caixa de
notificações, a visão inicial do Painel e as sugestões do menu **"Para você"**; os menus
"Atendimento" e "Gestão" continuam com todas as telas — é orientação, não controle de acesso.

### Relatórios e busca

Relatórios em `/app/relatorios` (JSON na tela, CSV para Excel e PDF). A busca global fica no topo
de todas as páginas (tecla `/`).

### Assistente educacional (IA)

Por padrão (`AI_PROVIDER=demo`) o assistente responde com regras determinísticas, sem rede e sem
chave de API. Para usar um modelo real:

```bash
pip install -r requirements-ai.txt
# no .env: AI_PROVIDER=anthropic e ANTHROPIC_API_KEY=<sua chave>   (nunca versione a chave)
```

As respostas são educacionais, não emitem diagnóstico e só recebem primeiro nome, idade e
registros clínicos do paciente fictício.

Roteiro de apresentação passo a passo: [`docs/DEMONSTRACAO.md`](docs/DEMONSTRACAO.md).
Dados de exemplo (médicos, enfermeiros, medicamentos, pacientes) e onde ver cada histórico:
[`docs/DADOS_DE_EXEMPLO.md`](docs/DADOS_DE_EXEMPLO.md).

## 📐 Especificações

Cada parte do sistema tem uma especificação em [`SPEC/`](SPEC), um arquivo por parte, com a data em que
foi escrita: `AAAA-MM-DD-<parte>.md` (o quê e por quê, modelo de dados, rotas, critérios de aceitação,
testes esperados e fora do escopo). Cada spec entra em um commit **anterior** ao código que ela
descreve, então o histórico do git mostra a ordem: spec, depois código. As specs de 2026-10-06 foram
escritas depois do código daquele dia; a regra vale a partir delas.

## ✅ Testes

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes usam bancos SQLite temporários e nunca alteram o `app.db`.
`tests/api/test_existing_endpoints.py` garante que os endpoints originais continuam funcionando.

Testes do frontend (Node 18+), em `tests/frontend`:

```bash
cd tests/frontend && npm install
npm test                                           # componentes de gráfico, sem servidor
HEALTHOS_URL=http://127.0.0.1:8000 npm run smoke   # todas as páginas contra a API em execução
HEALTHOS_URL=http://127.0.0.1:8000 npm run flow    # fluxos de interface: evolução, farmácia, portal
HEALTHOS_URL=http://127.0.0.1:8000 npm run a11y    # navegador real: WCAG 2.2 AA, 6 larguras, perfis, teclado
```

`npm run flow` e `npm run a11y` **gravam dados** (evolução, dispensação, agendamento, alerta): rode-os
com o servidor apontando para um banco descartável, por exemplo
`DATABASE_URL=sqlite:///./teste.db SEED_DEMO_DATA=True uvicorn main:app`.

No PowerShell, defina a variável antes: `$env:HEALTHOS_URL="http://127.0.0.1:8000"; npm run smoke`.
O `npm run a11y` usa o Edge ou o Chrome instalado (ou o caminho em `BROWSER_PATH`).

## 🩺 Observabilidade

| Endpoint   | Descrição                                                        |
|------------|------------------------------------------------------------------|
| `/health`  | Liveness: o processo está respondendo                            |
| `/status`  | Versão, uptime, conexão com o banco e contagem de registros      |
| `/metrics` | Requisições por rota, latência média/máxima e erros desde o boot |

## 🗂️ Estrutura

```
app/domain          entidades e regras de negócio
app/application     casos de uso, interfaces de repositório, DTOs
app/infrastructure  persistência, observabilidade, dados de demonstração
app/presentation    routers da API
static/             frontend modular (core/ e pages/)
tests/              unit/, integration/ e api/
docs/MODULOS.md     módulos, estados, regras e endpoints
docs/DECISOES.md    decisões arquiteturais (ADRs)
```

Mais detalhes em [ARCHITECTURE.md](ARCHITECTURE.md), [docs/MODULOS.md](docs/MODULOS.md) (regras de negócio e endpoints) e [docs/DECISOES.md](docs/DECISOES.md).
Informações técnicas e adições — HealthOS
Levantamento feito em 06/10/2026 sobre a branch feature/revisao-visual-acessibilidade (versão 1.10.0).

Projeto didático: todos os dados são fictícios, não há autenticação real e o sistema não emite diagnóstico médico.

1. Situação atual
Branch: feature/revisao-visual-acessibilidade, com 15 commits à frente da main.
Publicação: nada foi enviado ao GitHub nem publicado. O Render só atualiza quando a main do GitHub muda, então a produção continua na versão anterior.
Testes (todos passando na última execução):
200 testes Python (unidade, integração e API);
8 testes de componentes do frontend;
teste de fumaça de todas as páginas;
revisão de acessibilidade em navegador real (WCAG 2.1 AA, 4 larguras de tela).
Banco de dados: as adições só criam tabelas novas. Isso foi conferido subindo a aplicação sobre uma cópia do app.db: nenhuma linha perdida e nenhuma tabela existente alterada.
2. Linhas de código
Arquivos versionados no Git, sem node_modules, venv e arquivos gerados. "Linhas de código" exclui linhas em branco e comentários.

Parte	Arquivos	Linhas totais	Linhas de código
Python: aplicação (backend)	192	16.752	13.582
JavaScript: frontend	27	3.980	3.513
HTML	15	1.047	959
CSS	1	73	63
Subtotal do sistema	235	21.852	18.117
Python: testes	36	3.602	2.825
JavaScript: testes	4	449	381
Total com testes	275	25.903	21.323
Documentação (Markdown)	16	9.827	—
3. Funcionalidades
Números gerais
Item	Quantidade
Rotas da API documentadas em /docs	139 (62 de consulta e 77 de alteração)
Rotas de sistema (/, /health, /status, /metrics)	4
Páginas da interface	15 (portal + 14 em /app/...)
Tabelas no banco	52
Decisões de arquitetura registradas (docs/DECISOES.md)	25
Módulos
Módulo	O que faz
Pacientes e prontuário	Cadastro, busca, perfil, contatos de emergência, alergias, condições, diagnósticos, procedimentos e linha do tempo
Profissionais e consultas	Profissionais, especialidades, departamentos, horários de atendimento, agenda com situações e histórico de cada consulta
Sinais vitais	Registro com classificação e gráficos de evolução
Laboratório	Catálogo de exames, fluxo completo (solicitado até liberado), resultados com faixa de referência
Farmácia	Prescrição com checagem de alergia, dispensação por lote (vence primeiro, sai primeiro), estoque e validade
Eventos e auditoria	Trilha de auditoria, caixa de notificações por perfil e alertas por regra que se resolvem sozinhos
Painéis	Visões de paciente, profissional, farmácia e administração, e o Health Score demonstrativo
Assistente educacional (IA)	Resumo do prontuário, explicação de exames, orientação de sintomas e chat; funciona em modo demonstração, sem internet
Financeiro	Faturas, pagamentos parciais, "em atraso" pelo vencimento, faturamento de consultas e exames, indicadores
Relatórios	6 relatórios em JSON, CSV e PDF, com cada exportação registrada na auditoria
Busca global	Pacientes, profissionais, medicamentos, exames, faturas e relatórios, com CPF mascarado
Funções originais	Usuários e papéis, triagem, notificações e faturamento antigos, todos mantidos funcionando
Rotas da API por área
Área	Rotas
Prontuário eletrônico	18
Laboratório	14
Consultas	10
Assistente (IA educacional)	10
Profissionais de saúde	9
Financeiro	9
Serviços clínicos	8
Farmácia: estoque e lotes	8
Farmácia: prescrições e dispensações	8
Alertas por regra	6
Painéis e indicadores	5
Administração de usuários	4
Gestão de pacientes	4
Farmácia (original)	4
Faturamento (original)	4
Notificações internas	4
Notificações (original)	3
Sinais vitais	3
Alertas críticos (original)	2
Auditoria didática	2
Relatórios	2
Autenticação (original)	1
Busca	1
Total	139
4. Pontos de função (estimativa)
Não foi feita uma contagem formal. Os números abaixo são uma estimativa pelo método IFPUG, feita a partir das rotas da API e dos grupos de dados, com os pesos de complexidade média.

As 52 tabelas foram agrupadas em 33 grupos de dados. Por exemplo, a fatura com seus itens, pagamentos e cancelamentos conta como um único grupo.

Componente	Quantidade	Peso médio	Pontos
Arquivos internos (grupos de dados mantidos pelo sistema)	33	10	330
Arquivos externos (dados mantidos por outro sistema)	0	7	0
Entradas (cadastrar, alterar, registrar)	~73	4	~292
Saídas com cálculo (painéis, Health Score, relatórios, indicadores, respostas da IA)	~20	5	~100
Consultas (listagens e detalhes)	~50	4	~200
Total não ajustado			≈ 920 PF
Faixa provável: cerca de 680 PF se toda a complexidade fosse baixa e cerca de 1.370 PF se fosse alta.
Precisão: a estimativa tende a contar um pouco a mais, porque algumas rotas antigas repetem funções das novas (notificações, alertas e faturamento antigos convivem com os novos).
Contagem exata: exigiria listar, um a um, os processos que o usuário reconhece e classificar a complexidade de cada um.
5. Adições por ciclo
Cada ciclo foi feito em uma branch própria, criada a partir da anterior. A última branch contém todas as outras.

Versão	Branch	O que foi adicionado
1.0.x	fix/estabilizacao	Correção de erros 500 em endpoints existentes, de XSS no portal e restauração da suíte de testes
1.1.0	feature/base-observabilidade	Observabilidade (/health, /status, /metrics), frontend modular e dados de demonstração
1.2.0	feature/profissionais-consultas	Profissionais de saúde e consultas com controle de situações
1.3.0	feature/prontuario	Prontuário eletrônico com linha do tempo e busca de pacientes
1.4.0	feature/sinais-vitais-laboratorio	Sinais vitais com gráficos e laboratório com o fluxo completo de exames
1.5.0	feature/farmacia-prescricoes	Prescrição, dispensação por lote (vence primeiro, sai primeiro) e estoque por lote
1.6.0	feature/alertas-notificacoes-auditoria	Eventos de domínio, auditoria, notificações internas e alertas por regra
1.7.0	feature/dashboards-health-score	Painéis por perfil, Health Score demonstrativo e testes de frontend
1.8.0	feature/ia-chat	Assistente educacional com IA desacoplada (modo demonstração ou Claude) e chat com histórico
1.9.0	feature/relatorios-financeiro-busca	Financeiro ampliado, relatórios em JSON/CSV/PDF e busca global
1.10.0	feature/revisao-visual-acessibilidade	Navegação reorganizada, acessibilidade WCAG AA, revisão em navegador real e roteiro de demonstração
6. Tecnologias
Backend: Python 3.12, FastAPI, SQLAlchemy 2 (assíncrono), Pydantic 2; SQLite localmente e PostgreSQL como opção.
Frontend: JavaScript puro em módulos (sem framework nem etapa de build), Tailwind via CDN e gráficos SVG próprios.
PDF: fpdf2.
IA (opcional): SDK oficial da Anthropic. Por padrão roda em modo demonstração, sem rede.
Testes: pytest no backend; jsdom, puppeteer-core e axe-core no frontend.
Arquitetura: Clean Architecture, em quatro camadas (domínio, aplicação, infraestrutura e apresentação).
7. Documentos relacionados
README.md: como executar, gerar dados de demonstração e rodar os testes.
CHANGELOG.md: histórico de versões.
docs/MODULOS.md: detalhes de cada módulo e das rotas.
docs/DECISOES.md: decisões de arquitetura (ADR-001 a ADR-025).
docs/DEMONSTRACAO.md: roteiro de apresentação de 15 minutos.
## 🎓 Projeto acadêmico

Projeto desenvolvido para fins acadêmicos na disciplina de Análise e Desenvolvimento de Sistemas.

para verificar o link use: https://dsai-ap1-healthos.onrender.com/
