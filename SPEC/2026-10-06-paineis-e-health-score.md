# Painéis por perfil e Health Score (2026-10-06)

## O quê e por quê

Cada perfil precisa de uma visão rápida do que importa para ele: o paciente vê suas consultas, exames e medicamentos; o profissional vê a agenda e os exames alterados; a farmácia vê estoque, validade e fila; a administração vê números gerais.

O Health Score resume o quanto o paciente fictício está sendo **acompanhado** (comparecimento, exames concluídos, medicamentos retirados, monitoramento e seguimento), e não o quanto é saudável. É sempre apresentado como indicador demonstrativo, não diagnóstico (ADR-019).

## Modelo de dados (resumo)

Não há tabelas novas. Os painéis compõem os casos de uso existentes e usam um repositório de agregações para contagens e séries.

- **HealthScoreInputs** (fatos agregados): `completed_appointments`, `no_show_appointments`, `last_completed_appointment`, `has_upcoming_appointment`, `exams_requested`, `exams_released`, `exams_overdue`, `critical_exam_results`, `prescribed_quantity`, `dispensed_quantity`, `vitals_recent`, `latest_vitals_abnormal_ratio`, `active_conditions`. Janelas: 12 meses para consultas e exames, 90 dias para o resto.
- **HealthScore (resposta):** `patient_id`, `score` (0 a 100 ou nulo), `band`, `computed_at`, `disclaimer`, `components`.
- **Componente:** `key`, `label`, `score` (nulo = não aplicável), `applicable`, `explanation`. Chaves, nesta ordem: `consultas`, `exames`, `medicamentos`, `monitoramento`, `acompanhamento`.
- **Faixas (`ScoreBand`):** `BOM` (80 ou mais), `ATENCAO` (60 a 79), `INSUFICIENTE` (menos de 60).

## Rotas (`/api/v1`)

- `GET /patients/{patient_id}/health-score`
- `GET /dashboards/patient/{patient_id}`
- `GET /dashboards/professional/{professional_id}`
- `GET /dashboards/pharmacy`
- `GET /dashboards/admin`

Página da interface: `/app/painel` (visões Paciente, Profissional, Farmácia e Administração).

## Critérios de aceitação

### Health Score: componentes
- **Consultas:** percentual de comparecimento (finalizadas ÷ finalizadas + faltas). Sem consultas: não aplicável.
- **Exames:** liberados ÷ solicitados, menos 10 pontos por exame atrasado (no máximo 30). Sem exames: não aplicável. Valores críticos aparecem na explicação.
- **Medicamentos:** quantidade dispensada ÷ prescrita, limitada a 100%. Sem prescrição: não aplicável.
- **Monitoramento:** até 60 pontos pela regularidade (meta de 3 medições em 90 dias) e até 40 pela estabilidade (fração das medidas da última aferição dentro da referência). Sem nenhuma medição: vale 0.
- **Acompanhamento:** 100 se a última consulta finalizada foi há até 180 dias; 60 se foi há até 365; 20 caso contrário. Consulta futura agendada soma 20 (máximo 100).
- Com condição ativa, última consulta há mais de 180 dias e sem retorno marcado, a explicação avisa.

### Health Score: cálculo
- A nota final é a média arredondada só dos componentes aplicáveis. Ausência de dados não puxa a média para baixo.
- Cada componente fica entre 0 e 100.
- Exemplos verificáveis: paciente bem acompanhado tem nota 100 (`BOM`); paciente só com consulta futura tem acompanhamento 40, monitoramento 0 e nota 20.
- O cálculo é uma função pura de domínio, sem acesso a banco.
- A resposta sempre traz o aviso: "Indicador demonstrativo de acompanhamento, calculado com dados fictícios. Não é diagnóstico e não substitui avaliação profissional."
- Paciente inexistente retorna 404.

### Painel do paciente
- Traz nome, idade, Health Score, até 5 próximas consultas, medicamentos em uso, até 5 exames liberados, resumo dos sinais vitais, alertas abertos do paciente e quantidade de notificações não lidas.
- Paciente inexistente retorna 404.

### Painel do profissional
- Traz a agenda de hoje, a quantidade de consultas nos próximos 7 dias, consultas dos últimos 30 dias por estado, pacientes atendidos em 30 dias e taxa de comparecimento.
- A taxa de comparecimento é nula quando não há consulta finalizada nem falta.
- Traz exames solicitados por estado, até 10 exames alterados liberados em 30 dias e a série diária de 30 pontos (finalizadas, canceladas, faltas).
- Profissional inexistente retorna 404.

### Painel da farmácia
- Traz itens abaixo do mínimo, itens zerados, lotes vencendo em 30 dias, lotes vencidos e a fila de dispensação (prescrições `ATIVA` ou `PARCIALMENTE_DISPENSADA` não vencidas).
- Traz unidades dispensadas em 30 dias, série diária de 30 pontos, os 5 medicamentos mais dispensados e alertas abertos de estoque e medicamento.

### Painel da administração
- Traz contagens gerais, consultas de 30 dias por estado e por dia, exames de 90 dias por estado, prescrições de 30 dias e o resumo de alertas abertos.
- Traz novos pacientes nos últimos 6 meses (um ponto por mês, inclusive meses sem cadastro).
- Traz a distribuição do Health Score em `BOM`, `ATENCAO`, `INSUFICIENTE` e `SEM_DADOS`, e a média (nula se ninguém tiver nota).
- As entradas de todos os pacientes são calculadas em lote, sem uma consulta por paciente.
- Os agrupamentos por dia e por mês são feitos em Python, para funcionar igual em SQLite e PostgreSQL.

### Interface
- A página `/app/painel` mostra o Health Score com o rótulo "(indicador demonstrativo)" e exibe o aviso.
- A faixa aparece com ícone e texto, não só com cor.

## Testes esperados

- Unidade: `tests/unit/test_health_score.py` (paciente bem acompanhado, dado ausente como não aplicável, reação de cada componente, consulta futura e ausência de medições).
- Integração: `tests/integration/test_dashboards.py` (entradas conferidas com o banco, painéis de paciente, profissional, farmácia e administração, funções de série).
- API: `tests/api/test_dashboards_api.py` (ordem dos componentes, aviso, série de 30 dias, 6 meses no painel administrativo, 404 para paciente e profissional inexistentes).
- Frontend: `tests/frontend/pages.smoke.mjs` abre `/app/painel` e percorre as visões; `tests/frontend/components.test.mjs` testa os componentes de gráfico.

## Fora do escopo

- Qualquer uso clínico do Health Score: não é diagnóstico, risco nem prognóstico.
- Pesos configuráveis por usuário.
- Painéis com filtros de período livres (as janelas são fixas).
- Controle de acesso por perfil: a visão é escolhida na página, sem autenticação (ADR-002).
