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

```bash
python -m venv venv
venv\Scripts\activate            # Windows  (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # ajuste DATABASE_URL, ex.: sqlite:///./app.db
uvicorn main:app --reload
```

Acesse `http://127.0.0.1:8000/` (portal), `/app/painel`, `/app/prontuario`, `/app/consultas`, `/app/laboratorio`, `/app/farmacia`, `/app/alertas`,
`/app/assistente`, `/app/notificacoes`, `/app/auditoria`, `/app/profissionais`, `/app/status` e `/docs` (Swagger).

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

### Assistente educacional (IA)

Por padrão (`AI_PROVIDER=demo`) o assistente responde com regras determinísticas, sem rede e sem
chave de API. Para usar um modelo real:

```bash
pip install -r requirements-ai.txt
# no .env: AI_PROVIDER=anthropic e ANTHROPIC_API_KEY=<sua chave>   (nunca versione a chave)
```

As respostas são educacionais, não emitem diagnóstico e só recebem primeiro nome, idade e
registros clínicos do paciente fictício.

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
npm test                                  # componentes de gráfico, sem servidor
HEALTHOS_URL=http://127.0.0.1:8000 npm run smoke   # todas as páginas contra a API em execução
```

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