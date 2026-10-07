# Histórico de versões

Expansão incremental do HealthOS, um ciclo por branch (cada branch parte da anterior).
Detalhes de cada módulo em [`docs/MODULOS.md`](docs/MODULOS.md); decisões em [`docs/DECISOES.md`](docs/DECISOES.md).
Em todas as versões: dados fictícios, sem autenticação real e sem diagnóstico médico.

## 1.11.1 — Correções guiadas pelas specs
- Assistente: sinais de alerta recebem a orientação de urgência (SAMU 192) em qualquer provedor,
  sem chamar a IA (spec `2026-10-06-assistente-ia.md`, revisão).
- Faturamento: rota `POST /billing/invoices/{id}/pay`, prevista na spec de 2026-10-01 e nunca
  implementada; pagar fatura em rascunho passa a ser recusado (adendo em `2026-10-01-faturamento.md`).
- A partir desta versão, cada spec entra em um commit anterior ao código que ela descreve.

## 1.11.0 — Histórico dos profissionais e dados de exemplo
- Histórico de atividades no detalhe de cada profissional (consultas, sinais vitais, prescrições,
  dispensações, exames) e `GET /api/v1/professionals/{id}/activity`.
- Seed: os sinais vitais passam a ser registrados pela equipe de enfermagem.
- Falha no seed não impede mais a inicialização (registra o erro e segue).
- Seed conferido em PostgreSQL 16; dados de exemplo documentados em `docs/DADOS_DE_EXEMPLO.md`.

## 1.10.1 — Compatibilidade Linux/Render (`fix/compatibilidade-linux-render`)
- Python 3.13 fixado (`.python-version`, igual ao painel do Render) e dependências com versões
  exatas: o build deixa de depender das versões mais novas disponíveis no dia.
- Fuso horário configurável (`APP_TIMEZONE`, padrão `America/Belem`): o servidor Linux roda em UTC.
- `DATABASE_URL` do PostgreSQL do Render aceita sem ajuste manual.
- `render.yaml`, `Dockerfile` e README com instruções para Windows, Linux, Docker e Render. ADR-026.

## 1.10.0 — Revisão visual e acessibilidade (`feature/revisao-visual-acessibilidade`)
- Navegação reorganizada em Painel + menus "Atendimento" e "Gestão" e menu para celular
  (antes, metade das páginas ficava escondida em telas largas e todas sumiam no celular).
- Seletor de paciente utilizável só com teclado; gráficos com ARIA válido; contraste WCAG AA.
- `npm run a11y`: revisão automática em navegador real (axe, 4 larguras, teclado).
- Roteiro de demonstração em `docs/DEMONSTRACAO.md`. ADR-025.

## 1.9.0 — Financeiro, relatórios e busca (`feature/relatorios-financeiro-busca`)
- Pagamentos parciais, cancelamento com motivo, "em atraso" derivado do vencimento, faturamento
  de consultas e exames sem cobrança duplicada, indicadores e alerta de fatura vencida.
- Relatórios em JSON, CSV (Excel pt-BR) e PDF, com exportação auditada.
- Busca global com CPF mascarado e atalho `/`. ADR-022 a 024.
- **Nova dependência:** `fpdf2` (PDF).

## 1.8.0 — Assistente educacional com IA (`feature/ia-chat`)
- Resumo do prontuário, explicação de exames, orientação de sintomas com sinais de alerta e chat
  com histórico. Provedor `demo` (padrão, sem rede) ou `anthropic` (opcional). ADR-021.

## 1.7.0 — Painéis e Health Score (`feature/dashboards-health-score`)
- Painéis por perfil e Health Score demonstrativo; testes de frontend em DOM simulado.

## 1.6.0 — Eventos, auditoria, notificações e alertas (`feature/alertas-notificacoes-auditoria`)

## 1.5.0 — Farmácia (`feature/farmacia-prescricoes`)
- Prescrição, dispensação por lote (FEFO) e estoque por lote.

## 1.4.0 — Sinais vitais e laboratório (`feature/sinais-vitais-laboratorio`)

## 1.3.0 — Prontuário eletrônico (`feature/prontuario`)

## 1.2.0 — Profissionais e consultas (`feature/profissionais-consultas`)

## 1.1.0 — Base: observabilidade, frontend modular e dados de demonstração (`feature/base-observabilidade`)

## 1.0.x — Estabilização (`fix/estabilizacao`)
- Correção de erros 500 em endpoints existentes, XSS no portal e restauração da suíte de testes.

## Compatibilidade com o banco existente
Todas as versões só **criam tabelas novas** (no startup); nenhuma tabela existente é alterada ou
removida. Conferido a cada ciclo subindo a aplicação sobre uma cópia do `app.db`.
