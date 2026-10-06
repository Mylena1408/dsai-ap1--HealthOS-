# Módulos e regras de negócio

Visão de cada módulo do HealthOS: entidades, estados, regras e endpoints.
Todos os dados são fictícios; o sistema é didático.

---

## Módulos originais (preservados)

| Módulo | Endpoints (prefixo `/api/v1`) | Regras principais |
|---|---|---|
| Pacientes | `/admin/patients/` (POST, GET, GET/PATCH `{id}`) | CPF único e com 11 dígitos não repetidos; nascimento não pode ser futuro |
| Agenda legada | `/clinical/availability`, `/clinical/schedule`, `/clinical/patients/{id}/appointments` | Horários `AVAILABLE → BOOKED → CANCELED`; sem sobreposição por médico; duração entre 15 min e 12 h |
| Prontuário (notas) | `/clinical/notes`, `/clinical/notes/{id}`, `/clinical/notes/{id}/finalize`, `/clinical/patients/{id}/history` | Nota `DRAFT → FINALIZED`; nota finalizada é imutável; cada edição incrementa a versão |
| Alertas do paciente | `/admin/alerts/`, `/admin/alerts/patient/{id}/active` | Descrição com no mínimo 3 caracteres |
| Farmácia | `/pharmacy/medications`, `/pharmacy/inventory/{med}/{local}`, `/pharmacy/dispense/{med}/{local}`, `/pharmacy/critical-stock` | Saída nunca maior que o saldo; status `EM_ESTOQUE / ESTOQUE_BAIXO / ESGOTADO` pelo limite mínimo |
| Faturamento | `/billing/invoices`, `.../charges`, `.../finalize`, `/billing/patients/{id}/summary` | Fatura `RASCUNHO → PENDENTE → PAGO`; itens só em rascunho; não finaliza sem itens; coparticipação = total × (1 − cobertura) |
| Notificações | `/notifications/send`, `/notifications/me`, `/notifications/{id}/read` | Precisa de destinatário (usuário ou paciente); canal IN_APP é marcado como enviado na hora |

---

## Profissionais de saúde

**Entidades:** `Department`, `Specialty`, `Professional`, `WorkingHours`.

- Tipos: médico, enfermeiro, farmacêutico, nutricionista, fisioterapeuta, psicólogo, outro.
- Situação: `ATIVO`, `AFASTADO`, `INATIVO`. Só profissionais **ativos** recebem agendamentos.
- Registro profissional (fictício) é único. Nomes de departamento e especialidade são únicos (sem diferenciar maiúsculas).
- A grade semanal (`WorkingHours`) não pode ter janelas sobrepostas no mesmo dia; o início deve ser anterior ao fim.
- Cada especialidade define a **duração padrão** das consultas (10 a 240 min).

| Método | Endpoint | Descrição |
|---|---|---|
| GET/POST | `/departments` | Lista / cria departamento |
| GET/POST | `/specialties` | Lista / cria especialidade |
| GET | `/professionals?q=&professional_type=&status=&department_id=&specialty_id=&limit=&offset=` | Busca paginada |
| POST | `/professionals` | Cadastra (com grade opcional) |
| GET/PATCH | `/professionals/{id}` | Detalhes / atualização parcial |
| PUT | `/professionals/{id}/working-hours` | Substitui a grade semanal |
| GET | `/professionals/{id}/availability?date_from=&days=&duration_minutes=` | Horários livres |

---

## Consultas

Módulo independente da agenda legada (ver ADR-006 em `DECISOES.md`).

### Máquina de estados

```
AGENDADA ──► CONFIRMADA ──► EM_ANDAMENTO ──► FINALIZADA
   │  │          │  │
   │  └──────────┼──┴──► NAO_COMPARECEU   (somente após o horário marcado)
   └─────────────┴─────► CANCELADA        (somente antes do horário marcado)
```

- `FINALIZADA`, `CANCELADA` e `NAO_COMPARECEU` são estados finais. Ex.: **Cancelada → Em andamento é rejeitada** (HTTP 409).
- Iniciar o atendimento exige confirmação prévia e só é possível a partir de 30 min antes do horário.
- Cancelar exige motivo (mínimo de 3 caracteres).
- **Remarcar** é permitido em `AGENDADA`/`CONFIRMADA`; a consulta volta para `AGENDADA` (precisa ser reconfirmada).
- Toda mudança de estado é gravada no **histórico** (`appointment_status_history`), com data e observação.
- A resposta da API inclui `allowed_transitions`: as ações possíveis *agora*, já considerando o horário.

### Regras de agendamento

1. Paciente e profissional precisam existir; o profissional precisa estar ativo.
2. O horário deve ser futuro e caber inteiramente no expediente do profissional (se ele tiver grade cadastrada).
3. Duração: múltipla de 5, entre 10 e 240 min. Padrão: duração da especialidade, ou 30 min.
4. Sem sobreposição com consultas **ativas** (agendada, confirmada, em andamento) do mesmo profissional **ou** do mesmo paciente. Consultas canceladas liberam o horário.

**Horários livres** = janelas do expediente, fatiadas pela duração, menos consultas ativas e horários passados.

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/appointments?patient_id=&professional_id=&status=&date_from=&date_to=&newest_first=&limit=&offset=` | Busca paginada (`status` pode repetir) |
| POST | `/appointments` | Agenda |
| GET | `/appointments/{id}` | Detalhes com histórico |
| POST | `/appointments/{id}/confirm` · `/start` · `/complete` · `/no-show` | Transições |
| POST | `/appointments/{id}/cancel` | Cancela (`{"reason": "..."}`) |
| POST | `/appointments/{id}/reschedule` | Remarca (`{"start_time": "..."}`) |

### Códigos de erro dos módulos novos

| Situação | HTTP |
|---|---|
| Recurso inexistente | 404 |
| Regra de negócio violada (horário fora do expediente, passado etc.) | 400 |
| Conflito de agenda, duplicidade ou transição de estado inválida | 409 |
| Formato inválido (validação do Pydantic) | 422 |

---

## Observabilidade

`/health`, `/status` e `/metrics` — ver README.
