# Integração entre módulos (Fase 7, 2026-10-10)

Mapa das integrações do HealthOS: o que uma operação em um módulo provoca nos outros, com a
evidência de cada item. Parte da modernização da interface
(`SPEC/2026-10-10-modernizacao-visao-geral.md`). Nenhum código foi alterado nesta fase.

## Como foi verificado

- **Leitura do código:** casos de uso, eventos de domínio (`event_handlers.py`), regras de alerta
  (`alert_rules.py`), consultas de painéis, linha do tempo e faturamento.
- **Roteiro de ponta a ponta (I1):** script fora do repositório chamando a API real de um servidor
  local com banco temporário e dados de demonstração. 68 verificações: **60 confirmadas**, 8 não —
  todas as 8 nas lacunas legadas (L1 a L5).
- **Teste de integração existente (I2):** `tests/integration/test_patient_journey.py` — passou.

Legenda: ✅ integrado · ⚠️ integrado com ressalva · ❌ não integrado.

## Fluxos principais

| # | Fluxo | Situação | Evidência (I1) |
|---|---|---|---|
| 1 | Agendamento (`/appointments`) → caixas, auditoria, linha do tempo, painéis | ✅ | Consulta criada; `CONSULTA_AGENDADA` e `CONSULTA_CONFIRMADA` na auditoria; "Consulta agendada" (paciente) e "Nova consulta na sua agenda" (profissional); evento na linha do tempo; consulta no painel do paciente |
| 2 | Consulta finalizada → faturamento → pagamento | ✅ | Consulta aparece em "não faturado"; fatura criada sai da lista; segunda cobrança recusada (409); pagamento total deixa a fatura PAGA; `FATURA_EMITIDA` e `PAGAMENTO_REGISTRADO`; avisos ao paciente; fatura no Financeiro |
| 3 | Exame → laboratório → resultado → alerta | ✅ ⚠️ | Aviso ao Laboratório; coleta, processamento, resultado, validação e liberação; quatro eventos na auditoria; avisos ao paciente e ao solicitante; linha do tempo; exame em "não faturado"; alerta `EXAME_FORA_REFERENCIA` e aviso à Coordenação clínica. **Ressalva:** o alerta depende da avaliação periódica (15 min no Render) ou do botão de avaliar da tela Alertas (`POST /alerts/evaluate`) |
| 4 | Prescrição → farmácia → estoque | ✅ | Avisos à Farmácia, à Enfermagem e ao paciente; medicamento em uso no prontuário; prescrição na fila; dispensação com baixa por lote (FEFO); prescrição DISPENSADA; movimentação no estoque; `PRESCRICAO_EMITIDA` e `MEDICAMENTO_DISPENSADO`; linha do tempo; painel da Farmácia (+10 unidades) |
| 5 | Sinais vitais críticos → alerta | ✅ ⚠️ | Medição com autor; `SINAIS_VITAIS_REGISTRADOS`; linha do tempo; alerta `SINAL_VITAL_CRITICO` (o mesmo que o painel da Enfermagem lista). **Ressalva:** mesma dependência da avaliação periódica |
| 6 | Evolução clínica (Fase 3) | ✅ | Criada e assinada; `EVOLUCAO_ASSINADA`; linha do tempo; aparece no histórico legado `/clinical/patients/{id}/history` |

**Decisão, não lacuna:** dispensações não geram cobrança — o faturamento só conhece consultas e
exames (`ServiceSource`: CONSULTA, EXAME), como definido no ADR-022.

## Lacunas: rotas legadas

| # | Lacuna | Situação | Evidência | Tela afetada hoje |
|---|---|---|---|---|
| L1 | **Agenda legada** (`/clinical/schedule`, tabela `schedules`) separada das consultas (`appointments`) | ❌ | Reserva legada feita, mas **não aparece** em `/appointments`, no painel do paciente, na linha do tempo nem no faturamento; **nenhum evento** de auditoria (13 → 13) | **Sim:** "Agendar Consulta" e "Minhas Consultas" do portal |
| L2 | Faturamento legado (`POST /billing/invoices`) sem auditoria | ⚠️ | A fatura **aparece** no Financeiro (mesma tabela `invoices`), mas não gera evento | Não (nenhuma tela cria faturas por essa rota) |
| L3 | Dispensa legada (`/pharmacy/dispense`) sem receita nem auditoria | ⚠️ | Aceita sem receita; sem evento (a rota não informa paciente); os lotes são reconciliados na operação seguinte (movimentação `AJUSTE`, ADR-014) | Não (saiu do portal na Fase 5) |
| L4 | Notificações legadas (`/notifications`, tabela `notifications`) separadas da caixa de entrada (`inbox_notifications`) | ❌ | Notificação legada criada não aparece em `/inbox` | Não (o sino e a página Notificações usam `/inbox`) |
| L5 | **Alertas legados de paciente** (`/admin/alerts`, tabela `patient_alerts`) separados dos alertas por regra (`system_alerts`) | ⚠️ | Aparecem na linha do tempo do prontuário, mas **não** em `/alerts` (tela Alertas, painéis da Enfermagem e da Coordenação) nem no painel do paciente | **Sim:** "Alertas Críticos" do portal |

**Situação após as correções de 2026-10-10** (`SPEC/2026-10-10-portal-agenda-e-alertas.md`, commit
`8ba928f`):

- **L1 — corrigida nas telas:** o portal agenda e lista pelas consultas novas; a reserva aparece em
  Consultas, no painel, na linha do tempo e na auditoria (fluxo `portal.flow.mjs`). A rota legada
  `/clinical/schedule` continua na API, isolada como antes; reservas antigas ficam visíveis só para
  consulta no portal.
- **L5 — corrigida nas telas:** os alertas do portal aparecem no resumo do prontuário e no painel do
  paciente. Continuam fora de `/alerts` (alertas por regra).
- **L2 a L4:** rotas identificadas como "Legado" na descrição do Swagger; comportamento igual.

## Propostas mínimas (cada uma depende de aprovação)

| # | Proposta | Muda | Contratos |
|---|---|---|---|
| L1 | O portal passa a agendar pelas **consultas novas** (`GET /professionals/{id}/availability` + `POST /appointments`) e a listar "Minhas consultas" por `GET /appointments?patient_id=`. A rota legada fica na API | Só frontend (portal) | Nenhum muda |
| L5 | Mostrar os alertas legados ativos (`GET /admin/alerts/patient/{id}/active`, já existente) no resumo do prontuário e no painel do paciente | Só frontend | Nenhum muda |
| L2, L3, L4 | Marcar as rotas como "legado" na descrição do Swagger, sem mudar comportamento | Só textos da documentação da API | Nenhum muda |

Fora destas propostas: unificar tabelas legadas e novas (exigiria migração de dados, contra o
ADR-003).
