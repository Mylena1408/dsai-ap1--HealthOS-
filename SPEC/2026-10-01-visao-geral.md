# Visão geral (2026-10-01)

## O quê e por quê

HealthOS é um sistema integrado de gestão hospitalar, exposto como API REST (FastAPI) com uma página inicial simples. Ele acompanha o paciente da triagem e do agendamento ao prontuário, à farmácia e ao faturamento, com controle de acesso por perfil e registro de auditoria das alterações de dados.

O foco é a correção das regras de negócio (agenda sem conflito, prontuário imutável, estoque seguro, valores financeiros exatos) e a separação de camadas.

## Perfis de usuário

Perfis são papéis (`Role`) com permissões no formato `modulo:acao`. Perfis previstos: administrador, médico, enfermeiro e recepcionista. Permissões em uso nas rotas:

`user:create|read|update|delete`, `patient:read|write|update`, `clinical:read|write`, `pharmacy:read|write|dispense`, `billing:read|write`, `notification:read|write`.

## Partes do sistema (uma spec por parte)

1. `visao-geral` (este documento)
2. `usuarios-e-auth`
3. `pacientes-e-prontuario`
4. `agendamento`
5. `triagem`
6. `farmacia`
7. `faturamento`
8. `notificacoes`

## Arquitetura (restrições para todas as partes)

- Clean Architecture em quatro camadas: `domain`, `application`, `infrastructure` e `presentation`.
- O domínio é Python puro, sem importar FastAPI, SQLAlchemy ou Pydantic.
- Casos de uso dependem de interfaces de repositório. As implementações SQLAlchemy ficam na infraestrutura.
- Stack: Python 3.11+, FastAPI, SQLAlchemy 2.0 assíncrono, Pydantic v2, PyJWT. PostgreSQL (asyncpg) em produção e SQLite em testes.
- Rotas sob o prefixo `/api/v1`. A página inicial é servida em `/` e a documentação interativa em `/docs`.

## Critérios de aceitação gerais

- A aplicação abre em uma URL pública. `/` mostra a página inicial e `/docs` lista todas as rotas das 7 partes.
- Todo router implementado está registrado em `main.py`.
- Nenhuma entidade de domínio é criada em estado inválido: a validação ocorre em `__post_init__` ou no método de domínio que muda o estado.
- Erros de regra de negócio retornam resposta HTTP 4xx com mensagem clara, nunca erro 500.
- Valores monetários usam `Decimal`.
- Nenhum segredo é versionado: `SECRET_KEY` e `DATABASE_URL` vêm de variáveis de ambiente, com modelo em `.env.example`.
- `pytest tests/` executa sem erros de importação e todos os testes passam.

## Fora do escopo

- Integração com operadoras, SMS, e-mail e push reais.
- Interface gráfica completa.
- Assinatura digital de documentos clínicos.
- Pagamentos reais.
