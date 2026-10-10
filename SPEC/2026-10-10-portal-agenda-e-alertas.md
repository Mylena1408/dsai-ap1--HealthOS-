# Portal: agenda nas consultas novas e alertas visíveis (2026-10-10)

## O quê e por quê

Correções das lacunas L1 e L5 encontradas na Fase 7 (`docs/INTEGRACOES.md`):

- **L1:** o portal agendava pela agenda legada (`/clinical/schedule`, tabela `schedules`), que não
  aparece em Consultas, painéis, linha do tempo, faturamento nem auditoria.
- **L5:** os alertas criados no portal (`/admin/alerts`, tabela `patient_alerts`) só apareciam na
  linha do tempo.
- **L2 a L4:** rotas legadas sem uso nas telas passam a ser identificadas como legado no Swagger.

Decisão D8 = (a): reservas já feitas na agenda legada continuam visíveis, só para consulta.

## Modelo de dados (resumo)

Sem tabelas novas e sem mudança de comportamento no back-end.

## Rotas (`/api/v1`)

Sem rotas novas nem contratos alterados. O portal passa a usar:
`GET /professionals/{id}/availability`, `POST /appointments`, `GET /appointments?patient_id=`.
Prontuário e Painel passam a ler `GET /admin/alerts/patient/{id}/active`.

Só a **descrição** no Swagger muda (texto "Legado: ...") em: `POST /billing/invoices`,
`POST /billing/invoices/{id}/charges`, `POST /billing/invoices/{id}/finalize`,
`POST /billing/invoices/{id}/pay`, `POST /pharmacy/dispense/{med}/{loc}`, `POST /notifications/send`,
`GET /notifications/me` e `PATCH /notifications/{id}/read`.

## Critérios de aceitação

### Agendar (portal)
- Médico escolhido numa lista (sugerido pelo perfil, se for médico); os horários livres dos próximos
  7 dias carregam ao escolher o médico (ou pelo botão), agrupados por dia.
- Reserva com paciente, médico, horário e motivo opcional; a consulta criada aparece em Consultas,
  no painel do paciente, na linha do tempo e na auditoria (`CONSULTA_AGENDADA`).
- Sem paciente ou sem horário, a mensagem aparece no formulário e nada é enviado.

### Minhas consultas (portal)
- Lista as consultas do paciente (`/appointments`) com data, profissional e situação.
- Seção "Reservas da agenda antiga (somente consulta)" com as reservas legadas, se houver.

### Alertas do paciente
- Resumo do prontuário: cartão "Alertas do paciente" com os alertas legados ativos (tipo, gravidade
  em texto e ícone, descrição).
- Painel › Paciente: os mesmos alertas, junto dos alertas abertos.

## Testes esperados

- `npm run flow` (`portal.flow.mjs`): agendar pelo portal e conferir em `/appointments`, auditoria e
  painel; "Minhas consultas" com a consulta nova; alerta do portal no resumo do prontuário e no painel.
- `pytest` (inclui o Swagger: `GET /openapi.json` com as descrições de legado), `npm test`,
  `npm run smoke`, `npm run a11y`.

## Fora do escopo

- Migrar reservas legadas para consultas (ADR-003).
- Mudar ou remover rotas legadas.
