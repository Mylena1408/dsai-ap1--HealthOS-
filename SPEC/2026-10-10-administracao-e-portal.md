# Administração e portal sem IDs digitados (2026-10-10)

## O quê e por quê

Fase 6 da modernização (`2026-10-10-modernizacao-visao-geral.md`). O portal (`index.html`) pedia
sete identificadores digitados à mão (seis de paciente e um de médico), mostrava erros com
`alert()` e guardava o ID do paciente no navegador. A visão "Administração" do Painel mostrava
indicadores clínicos (Health Score, exames) e nenhum financeiro. Decisão D6 = (a).

## Modelo de dados (resumo)

Sem tabelas e sem rotas novas. O portal continua usando as rotas legadas, sem mudar contratos.

- Paciente do portal: escolhido pelo seletor de paciente (`createPatientPicker`) e mantido só na
  memória da página; com o perfil de paciente, vem preenchido. A chave `healthos.patientId` deixa
  de ser gravada (R6).
- Médico da nota: lista de médicos ativos (`GET /professionals?professional_type=MEDICO&status=ATIVO`).

## Rotas (`/api/v1`)

Sem rotas novas. Passam a ser usadas: `GET /patients?q=` (seletor), `GET /professionals`,
`GET /billing/summary` e `GET /dashboards/admin` (visão Administração). As rotas legadas do portal
continuam: `/admin/patients`, `/clinical/*`, `/billing/patients/{id}/summary`, `/admin/alerts`.

## Critérios de aceitação

### Portal
- Nenhum campo pede ID digitado. Em Minhas consultas, Agendar, Faturas, Histórico, Nova evolução e
  Alertas, o paciente é escolhido por nome ou CPF; a escolha vale para todos os formulários.
- Nova evolução: médico escolhido na lista (sugerido pelo perfil, se for médico). Com ID de
  profissional, a nota vira evolução (ponte da Fase 3) e aparece no histórico.
- Sem paciente escolhido, a ação mostra a mensagem no próprio formulário e não chama a API.
- Nenhum `alert()`: erros e resultados aparecem junto da operação.
- Depois do cadastro, o paciente novo fica escolhido nos formulários e o ID continua visível.
- Visão inicial: perfil de paciente abre "Paciente"; perfil profissional abre "Médico"; setores
  mantêm "Paciente".

### Visão Administração (Painel)
- Indicadores: pacientes, consultas (30 dias), a receber e vencido (com quantidade de faturas).
- Gráficos: consultas por dia, novos pacientes por mês, faturas por situação, alertas abertos por
  categoria.
- Atalhos: Consultas, Financeiro, Relatórios, Profissionais.
- Health Score e exames saem desta visão (continuam nas visões de paciente e profissional).

## Testes esperados

- `npm run flow` (`tests/frontend/portal.flow.mjs`): escolher paciente pelo nome e consultar
  consultas, faturas e histórico; agendar; nota com médico da lista vira evolução; alerta; perfil de
  paciente preenche o paciente; nenhum `alert()`; sem paciente, mensagem no formulário; visão
  Administração com indicadores financeiros e sem Health Score.
- Regressão: `npm test`, `npm run smoke`, `npm run a11y`, `pytest`.

## Fora do escopo

- Mudanças no back-end ou nas rotas legadas.
- Cadastro de pacientes fora do portal.
