# Painel da enfermagem (2026-10-10)

## O quê e por quê

Fase 4 da modernização (`2026-10-10-modernizacao-visao-geral.md`), opção B da decisão D3: uma
visão "Enfermagem" no Painel montada só com o que a API já oferece. Antes, o perfil Enfermeiro
caía na visão genérica "Profissional" e o setor Enfermagem na de "Administração".

## Modelo de dados (resumo)

Sem tabelas e sem rotas novas. Estruturas do frontend:

- **`dashboardViewFor(profile)`** (`static/js/core/role-nav.js`): visão inicial do Painel por perfil —
  paciente → `patient`; enfermeiro (tipo `ENFERMEIRO`) ou setor `ENFERMAGEM` → `nursing`; outros
  profissionais → `professional`; setor `FARMACIA` → `pharmacy`; demais setores → `admin`.
- **`renderNursingBoard`** (`static/js/pages/dashboard-nursing.js`): a visão "Enfermagem".

## Rotas (`/api/v1`)

Sem rotas novas. Usadas (já existentes, só leitura):

- `GET /appointments?date_from=<hoje>&date_to=<hoje>&status=AGENDADA&status=CONFIRMADA&status=EM_ANDAMENTO&status=FINALIZADA`
- `GET /alerts?rule_code=SINAL_VITAL_CRITICO&status=ATIVO&status=RECONHECIDO`
- `GET /prescriptions?status=ATIVA&status=PARCIALMENTE_DISPENSADA`
- `GET /inbox/counts?audience=SETOR&sector=ENFERMAGEM`

"Hoje" é a data local do navegador.

## Critérios de aceitação

- A aba "Enfermagem" aparece entre "Profissional" e "Farmácia" no Painel, para qualquer perfil.
- Perfil Enfermeiro ou setor Enfermagem abre o Painel já na visão "Enfermagem".
- Quatro indicadores: consultas de hoje, sinais vitais críticos em aberto, prescrições ativas e
  avisos não lidos do setor (com link para Notificações).
- "Pacientes do dia": horário, paciente, profissional, situação e "Abrir prontuário".
- "Sinais vitais críticos": alertas em aberto (ativos ou reconhecidos), com nível em texto e ícone e
  link para o prontuário do paciente.
- "Prescrições ativas": paciente, prescritor, itens (medicamento, dose e frequência) e link para o
  prontuário; aviso de que a administração de medicamentos não é registrada no sistema.
- Listas vazias mostram mensagem; falhas mostram o erro como nas outras visões.

## Testes esperados

- `npm test`: `dashboardViewFor` para todos os perfis.
- `npm run smoke`: "painel › enfermagem".
- `npm run flow`: perfil de enfermagem abre a visão, mostra os quatro indicadores e os links levam
  ao prontuário.
- `npm run a11y` e `pytest` (regressão).

## Fora do escopo

- Qualquer mudança no back-end.
- Triagem, tarefas de enfermagem, registro de cuidados e checagem de medicamentos (sem modelos nem
  regras no sistema).
