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

## Prontuário eletrônico

Tabelas novas ligadas ao paciente legado: `patient_profiles` (1:1), `patient_emergency_contacts`,
`patient_allergies`, `patient_conditions`, `patient_diagnoses`, `patient_procedures`.

| Registro | Regras |
|---|---|
| Perfil | Tipo sanguíneo (`A+` … `O-`, `NAO_INFORMADO`), ocupação, observações |
| Contatos de emergência | No máximo 3; telefone com 10 a 13 dígitos; **sempre exatamente um principal** (o primeiro cadastrado ou o marcado; ao remover o principal, outro assume) |
| Alergias | Categoria (medicamento, alimento, ambiental, outro) e gravidade (leve, moderada, grave). **Não pode haver duas alergias ativas à mesma substância** (sem diferenciar maiúsculas/espaços). `ATIVA → RESOLVIDA` uma única vez |
| Condições | `ATIVA ⇄ CONTROLADA → RESOLVIDA`, e `RESOLVIDA → ATIVA` (recidiva). Início não pode ser futuro nem anterior ao nascimento; resolução não pode ser anterior ao início |
| Diagnósticos | Certeza `SUSPEITA → CONFIRMADA` ou `SUSPEITA → DESCARTADA` (somente hipóteses mudam). Se vinculado a uma consulta, ela deve ser do mesmo paciente e não pode estar cancelada/não comparecida; sem profissional informado, herda o da consulta |
| Procedimentos | Data de realização não pode ser futura; mesmas regras de vínculo com consulta |

### Linha do tempo

Reúne, em ordem cronológica, eventos de **todas** as fontes: cadastro, consultas, notas
clínicas (legado), alertas (legado), triagens (legado), alergias (registro e resolução),
condições (início e resolução), diagnósticos e procedimentos. Filtros por tipo e período;
ordem crescente ou decrescente; paginação.

> Limitação conhecida: tabelas legadas preenchem `created_at` com `func.now()` do banco,
> que no SQLite é UTC; por isso cadastro, alertas e triagens podem aparecer deslocados em
> relação ao horário local.

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/patients?q=&order_by=name\|recent&limit=&offset=` | Busca paginada (nome, CPF ou e-mail) |
| GET | `/patients/{id}/record` | Resumo: dados, perfil, alergias ativas, problemas ativos, diagnósticos recentes, próximas consultas e última consulta |
| GET | `/patients/{id}/timeline?types=&date_from=&date_to=&newest_first=&limit=&offset=` | Linha do tempo |
| PUT | `/patients/{id}/profile` | Atualiza o perfil |
| POST / DELETE | `/patients/{id}/emergency-contacts[/{contact_id}]` | Adiciona / remove contato |
| GET / POST | `/patients/{id}/allergies` · POST `.../{allergy_id}/resolve` | Alergias |
| GET / POST | `/patients/{id}/conditions` · PATCH `.../{condition_id}/status` | Condições |
| GET / POST | `/patients/{id}/diagnoses` · POST `.../{id}/confirm` · `.../{id}/rule-out` | Diagnósticos |
| GET / POST | `/patients/{id}/procedures` | Procedimentos |

---

## Sinais vitais

Tabela `vital_signs`. Cada registro tem ao menos uma medida; valores fora de limites
fisiológicos plausíveis são rejeitados (ex.: temperatura fora de 30–45 °C); pressão exige
sistólica **e** diastólica, com sistólica maior; a data não pode ser futura nem anterior ao
nascimento.

| Métrica | Unidade | Faixa normal (ilustrativa) | Crítico |
|---|---|---|---|
| Pressão sistólica / diastólica | mmHg | 90–129 / 60–84 | < 70 ou > 180 / < 40 ou > 120 |
| Frequência cardíaca | bpm | 60–100 | < 40 ou > 130 |
| Frequência respiratória | irpm | 12–20 | < 8 ou > 30 |
| Temperatura | °C | 35,5–37,7 | < 34 ou > 40 |
| Saturação de O₂ | % | ≥ 95 | < 90 |
| Glicemia capilar | mg/dL | 70–99 | < 54 ou > 300 |
| IMC (derivado) | kg/m² | 18,5–24,9 | — |

- **IMC** usa o peso do registro e a altura do próprio registro **ou a última altura conhecida**.
- Classificação de cada medida: `NORMAL`, `BAIXO`, `ALTO`, `CRITICO_BAIXO`, `CRITICO_ALTO`.
- O resumo traz a última medida, a anterior e a **tendência** (`SUBINDO`/`DESCENDO`/`ESTAVEL`,
  com tolerância de 2%) e a série temporal das últimas 30 medições, para os gráficos.

| Método | Endpoint |
|---|---|
| POST / GET | `/patients/{id}/vital-signs` (lista paginada, filtro por período) |
| GET | `/patients/{id}/vital-signs/summary` |

## Laboratório

Tabelas `laboratories`, `exam_types`, `exam_analytes`, `exam_requests`, `exam_results`,
`exam_request_status_history`. O **catálogo** (11 exames: hemograma, glicemia, HbA1c, perfil
lipídico, triglicerídeos, creatinina, ureia, potássio, TSH, T4 livre, vitamina D) é dado de
referência e é criado no startup de forma idempotente.

```
SOLICITADO ─► AGENDADO ─► COLETADO ─► EM_PROCESSAMENTO ─► RESULTADO_REGISTRADO ─► VALIDADO ─► LIBERADO
   │  │          │ ▲ │                      ▲                       │
   │  └──────────┼─┘ │ (reagendar)          └── devolvido p/ correção ┘
   └─────────────┴───┴─► CANCELADO   (apenas antes da coleta)
```

- Coleta pode ocorrer direto da solicitação (coleta imediata) e gera o **código da amostra**.
- Resultados exigem **todos** os analitos do exame, nenhum a mais, dentro de limites plausíveis;
  cada valor é classificado contra a faixa de referência.
- Unidade e referência são **copiadas para o resultado** no registro: alterar o catálogo depois
  não muda laudos antigos.
- Validação exige profissional **ativo**; o validador pode **devolver** o laudo (resultados descartados).
- Só resultados **liberados** aparecem para o paciente (aba Exames, linha do tempo e evolução do analito).
- Prazo previsto = coleta + prazo do tipo de exame.

| Método | Endpoint |
|---|---|
| GET | `/exam-types`, `/laboratories` |
| GET / POST | `/exam-requests` (filtros: paciente, status (repetível), tipo, prioridade, período, `only_abnormal`) |
| GET | `/exam-requests/{id}` |
| POST | `/exam-requests/{id}/schedule` · `/collect` · `/start-processing` · `/results` · `/validate` · `/return` · `/release` · `/cancel` |
| GET | `/patients/{id}/exams/analytes/{codigo}/history` |

A linha do tempo do prontuário passa a incluir `SINAIS_VITAIS` (com indicação de valores
alterados) e `EXAME` (solicitação e liberação, listando os analitos fora da referência).

> Todas as faixas são **ilustrativas** (adulto genérico, sem distinção por sexo/idade/método)
> e não servem para interpretação clínica real.

---

## Farmácia: prescrição, dispensação e estoque por lote

Fluxo: **consulta → prescrição → farmácia → dispensação → baixa no estoque**.
Tabelas novas: `medication_categories`, `medication_details` (1:1 com `medications`),
`stock_lots`, `inventory_movements`, `prescriptions`, `prescription_items`, `dispensations`,
`dispensation_lines`. As tabelas e rotas legadas (`/pharmacy/...`) continuam iguais.

### Estoque

- **Total por medicamento/local continua em `inventory_items` (legado)**; os lotes detalham parte
  dele e o restante é "estoque sem lote" (ADR-014). Invariante: soma dos lotes ≤ total.
- **Entrada** só por lote (`POST /stock/lots`): número do lote único por medicamento/local
  (normalizado em maiúsculas), validade futura; o total legado é atualizado junto.
- **Saída FEFO**: lotes válidos do vencimento mais próximo ao mais distante, estoque sem lote por
  último; **lote vencido nunca é usado**.
- **Reconciliação**: saídas feitas pelo endpoint legado mexem só no total; antes de qualquer
  operação nova, a diferença é baixada dos lotes por FEFO e registrada como `AJUSTE`.
- **Descarte**: livre para lote vencido; dentro da validade exige justificativa (≥ 10 caracteres).
- Toda mudança gera uma **movimentação** (`ENTRADA`, `DISPENSACAO`, `AJUSTE`, `DESCARTE`) com o
  saldo após a operação. Medicamento **descontinuado** não recebe lotes nem pode ser prescrito.

### Prescrição

```
Prescrição:  ATIVA ─► PARCIALMENTE_DISPENSADA ─► DISPENSADA
               └──────────────┴─────────────────► CANCELADA
Item:        EM_USO ⇄ SUSPENSO ;  EM_USO ─► CONCLUIDO
```

- Somente **médicos ativos** prescrevem; vínculo opcional com consulta do mesmo paciente.
- Sem medicamento repetido; quantidade de 1 a 1000; duração de 1 a 365 dias.
- **Controle especial** (substância controlada): no máximo 60 unidades por item; a receita é marcada.
- **Alergia**: se o paciente tem alergia **ativa** cujo texto corresponde ao nome ou princípio
  ativo, a prescrição é bloqueada (409) — salvo com **justificativa** (≥ 10 caracteres), que fica
  registrada e aparece para a farmácia.
- Validade de **30 dias**; receita vencida não é dispensada.
- "Medicamentos do paciente" = itens de prescrições não canceladas (em uso, suspensos, concluídos).

### Dispensação

- Somente **farmacêuticos ativos**; apenas itens **em uso**, até o saldo prescrito.
- A baixa ocorre por FEFO e cada linha registra o lote utilizado (ou "sem lote").
- Falha em qualquer item desfaz a dispensação inteira (transação).
- O status da prescrição é recalculado (parcial / dispensada). Itens suspensos não bloqueiam a conclusão.

| Método | Endpoint |
|---|---|
| GET / POST | `/medication-categories` |
| GET | `/medications/stock?q=&category_id=&low_stock_only=` |
| PUT | `/medications/{id}/details` |
| GET / POST | `/stock/lots` (`expiring_within_days`, `medication_id`, `location`) · POST `/stock/lots/{id}/discard` |
| GET | `/stock/movements` |
| GET / POST | `/prescriptions` · GET `/prescriptions/{id}` · POST `/prescriptions/{id}/cancel` |
| POST | `/prescriptions/{id}/items/{item_id}/suspend` · `/resume` · `/complete` |
| GET / POST | `/dispensations` |
| GET | `/patients/{id}/medications?status=` |

A linha do tempo inclui `PRESCRICAO` e `DISPENSACAO`.

---

## Observabilidade

`/health`, `/status` e `/metrics` — ver README.
