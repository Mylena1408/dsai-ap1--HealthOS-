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

Não há login: o **perfil de demonstração** (canto superior direito) escolhe se a caixa de
notificações exibida é de um paciente, de um profissional ou de um setor.

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
HEALTHOS_URL=http://127.0.0.1:8000 npm run a11y    # navegador real: acessibilidade, 4 larguras, teclado
```

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

## 🎓 Projeto acadêmico

Projeto desenvolvido para fins acadêmicos na disciplina de Análise e Desenvolvimento de Sistemas.

para verificar o link use: https://dsai-ap1-healthos.onrender.com/