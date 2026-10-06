# Informações técnicas e adições — HealthOS

*Levantamento feito em 06/10/2026 sobre a branch `feature/revisao-visual-acessibilidade` (versão 1.10.0).*

> Projeto didático: todos os dados são fictícios, não há autenticação real e o sistema não emite
> diagnóstico médico.

## 1. Situação atual

- **Branch:** `feature/revisao-visual-acessibilidade`, com 15 commits à frente da `main`.
- **Publicação:** nada foi enviado ao GitHub nem publicado. O Render só atualiza quando a `main` do
  GitHub muda, então a produção continua na versão anterior.
- **Testes (todos passando na última execução):**
  - 200 testes Python (unidade, integração e API);
  - 8 testes de componentes do frontend;
  - teste de fumaça de todas as páginas;
  - revisão de acessibilidade em navegador real (WCAG 2.1 AA, 4 larguras de tela).
- **Banco de dados:** as adições só criam tabelas novas. Isso foi conferido subindo a aplicação
  sobre uma cópia do `app.db`: nenhuma linha perdida e nenhuma tabela existente alterada.

## 2. Linhas de código

Arquivos versionados no Git, sem `node_modules`, `venv` e arquivos gerados. "Linhas de código"
exclui linhas em branco e comentários.

| Parte | Arquivos | Linhas totais | Linhas de código |
|---|---:|---:|---:|
| Python: aplicação (backend) | 192 | 16.752 | 13.582 |
| JavaScript: frontend | 27 | 3.980 | 3.513 |
| HTML | 15 | 1.047 | 959 |
| CSS | 1 | 73 | 63 |
| **Subtotal do sistema** | **235** | **21.852** | **18.117** |
| Python: testes | 36 | 3.602 | 2.825 |
| JavaScript: testes | 4 | 449 | 381 |
| **Total com testes** | **275** | **25.903** | **21.323** |
| Documentação (Markdown) | 16 | 9.827 | — |

## 3. Funcionalidades

### Números gerais

| Item | Quantidade |
|---|---:|
| Rotas da API documentadas em `/docs` | 139 (62 de consulta e 77 de alteração) |
| Rotas de sistema (`/`, `/health`, `/status`, `/metrics`) | 4 |
| Páginas da interface | 15 (portal + 14 em `/app/...`) |
| Tabelas no banco | 52 |
| Decisões de arquitetura registradas (`docs/DECISOES.md`) | 25 |

### Módulos

| Módulo | O que faz |
|---|---|
| Pacientes e prontuário | Cadastro, busca, perfil, contatos de emergência, alergias, condições, diagnósticos, procedimentos e linha do tempo |
| Profissionais e consultas | Profissionais, especialidades, departamentos, horários de atendimento, agenda com situações e histórico de cada consulta |
| Sinais vitais | Registro com classificação e gráficos de evolução |
| Laboratório | Catálogo de exames, fluxo completo (solicitado até liberado), resultados com faixa de referência |
| Farmácia | Prescrição com checagem de alergia, dispensação por lote (vence primeiro, sai primeiro), estoque e validade |
| Eventos e auditoria | Trilha de auditoria, caixa de notificações por perfil e alertas por regra que se resolvem sozinhos |
| Painéis | Visões de paciente, profissional, farmácia e administração, e o Health Score demonstrativo |
| Assistente educacional (IA) | Resumo do prontuário, explicação de exames, orientação de sintomas e chat; funciona em modo demonstração, sem internet |
| Financeiro | Faturas, pagamentos parciais, "em atraso" pelo vencimento, faturamento de consultas e exames, indicadores |
| Relatórios | 6 relatórios em JSON, CSV e PDF, com cada exportação registrada na auditoria |
| Busca global | Pacientes, profissionais, medicamentos, exames, faturas e relatórios, com CPF mascarado |
| Funções originais | Usuários e papéis, triagem, notificações e faturamento antigos, todos mantidos funcionando |

### Rotas da API por área

| Área | Rotas |
|---|---:|
| Prontuário eletrônico | 18 |
| Laboratório | 14 |
| Consultas | 10 |
| Assistente (IA educacional) | 10 |
| Profissionais de saúde | 9 |
| Financeiro | 9 |
| Serviços clínicos | 8 |
| Farmácia: estoque e lotes | 8 |
| Farmácia: prescrições e dispensações | 8 |
| Alertas por regra | 6 |
| Painéis e indicadores | 5 |
| Administração de usuários | 4 |
| Gestão de pacientes | 4 |
| Farmácia (original) | 4 |
| Faturamento (original) | 4 |
| Notificações internas | 4 |
| Notificações (original) | 3 |
| Sinais vitais | 3 |
| Alertas críticos (original) | 2 |
| Auditoria didática | 2 |
| Relatórios | 2 |
| Autenticação (original) | 1 |
| Busca | 1 |
| **Total** | **139** |

## 4. Pontos de função (estimativa)

Não foi feita uma contagem formal. Os números abaixo são uma **estimativa pelo método IFPUG**,
feita a partir das rotas da API e dos grupos de dados, com os pesos de complexidade média.

As 52 tabelas foram agrupadas em 33 grupos de dados. Por exemplo, a fatura com seus itens,
pagamentos e cancelamentos conta como um único grupo.

| Componente | Quantidade | Peso médio | Pontos |
|---|---:|---:|---:|
| Arquivos internos (grupos de dados mantidos pelo sistema) | 33 | 10 | 330 |
| Arquivos externos (dados mantidos por outro sistema) | 0 | 7 | 0 |
| Entradas (cadastrar, alterar, registrar) | ~73 | 4 | ~292 |
| Saídas com cálculo (painéis, Health Score, relatórios, indicadores, respostas da IA) | ~20 | 5 | ~100 |
| Consultas (listagens e detalhes) | ~50 | 4 | ~200 |
| **Total não ajustado** | | | **≈ 920 PF** |

- **Faixa provável:** cerca de 680 PF se toda a complexidade fosse baixa e cerca de 1.370 PF se
  fosse alta.
- **Precisão:** a estimativa tende a contar um pouco a mais, porque algumas rotas antigas repetem
  funções das novas (notificações, alertas e faturamento antigos convivem com os novos).
- **Contagem exata:** exigiria listar, um a um, os processos que o usuário reconhece e classificar a
  complexidade de cada um.

## 5. Adições por ciclo

Cada ciclo foi feito em uma branch própria, criada a partir da anterior. A última branch contém
todas as outras.

| Versão | Branch | O que foi adicionado |
|---|---|---|
| 1.0.x | `fix/estabilizacao` | Correção de erros 500 em endpoints existentes, de XSS no portal e restauração da suíte de testes |
| 1.1.0 | `feature/base-observabilidade` | Observabilidade (`/health`, `/status`, `/metrics`), frontend modular e dados de demonstração |
| 1.2.0 | `feature/profissionais-consultas` | Profissionais de saúde e consultas com controle de situações |
| 1.3.0 | `feature/prontuario` | Prontuário eletrônico com linha do tempo e busca de pacientes |
| 1.4.0 | `feature/sinais-vitais-laboratorio` | Sinais vitais com gráficos e laboratório com o fluxo completo de exames |
| 1.5.0 | `feature/farmacia-prescricoes` | Prescrição, dispensação por lote (vence primeiro, sai primeiro) e estoque por lote |
| 1.6.0 | `feature/alertas-notificacoes-auditoria` | Eventos de domínio, auditoria, notificações internas e alertas por regra |
| 1.7.0 | `feature/dashboards-health-score` | Painéis por perfil, Health Score demonstrativo e testes de frontend |
| 1.8.0 | `feature/ia-chat` | Assistente educacional com IA desacoplada (modo demonstração ou Claude) e chat com histórico |
| 1.9.0 | `feature/relatorios-financeiro-busca` | Financeiro ampliado, relatórios em JSON/CSV/PDF e busca global |
| 1.10.0 | `feature/revisao-visual-acessibilidade` | Navegação reorganizada, acessibilidade WCAG AA, revisão em navegador real e roteiro de demonstração |

## 6. Tecnologias

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 (assíncrono), Pydantic 2; SQLite localmente e
  PostgreSQL como opção.
- **Frontend:** JavaScript puro em módulos (sem framework nem etapa de build), Tailwind via CDN e
  gráficos SVG próprios.
- **PDF:** fpdf2.
- **IA (opcional):** SDK oficial da Anthropic. Por padrão roda em modo demonstração, sem rede.
- **Testes:** pytest no backend; jsdom, puppeteer-core e axe-core no frontend.
- **Arquitetura:** Clean Architecture, em quatro camadas (domínio, aplicação, infraestrutura e
  apresentação).

## 7. Documentos relacionados

- `README.md`: como executar, gerar dados de demonstração e rodar os testes.
- `CHANGELOG.md`: histórico de versões.
- `docs/MODULOS.md`: detalhes de cada módulo e das rotas.
- `docs/DECISOES.md`: decisões de arquitetura (ADR-001 a ADR-025).
- `docs/DEMONSTRACAO.md`: roteiro de apresentação de 15 minutos.
