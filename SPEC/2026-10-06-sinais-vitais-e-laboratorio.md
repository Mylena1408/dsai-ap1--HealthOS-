# Sinais vitais e laboratório (2026-10-06)

## O quê e por quê

O prontuário precisa acompanhar medidas do paciente ao longo do tempo e o ciclo completo de um exame, da solicitação à liberação do resultado. Esta parte registra sinais vitais com classificação didática de cada medida e controla as solicitações de exame por uma máquina de estados.

Todas as faixas de referência são ILUSTRATIVAS (adulto genérico, sem distinção por sexo, idade ou método). Os valores e resultados são fictícios e não servem para interpretação clínica real.

## Modelo de dados (resumo)

- **Tabelas novas:** `vital_signs`, `laboratories`, `exam_types`, `exam_analytes`, `exam_requests`, `exam_results`, `exam_request_status_history`.
- **VitalSigns:** `patient_id`, `recorded_at`, `systolic`, `diastolic`, `heart_rate`, `respiratory_rate`, `temperature`, `oxygen_saturation`, `weight_kg`, `height_cm`, `glucose_mg_dl`, `professional_id`, `notes` (até 500 caracteres).
- **Métricas (`VitalMetric`):** `systolic`, `diastolic`, `heart_rate`, `respiratory_rate`, `temperature`, `oxygen_saturation`, `weight_kg`, `height_cm`, `glucose_mg_dl`, `bmi`.
- **Categoria do IMC (`BmiCategory`):** `BAIXO_PESO` (< 18,5), `PESO_ADEQUADO` (< 25), `SOBREPESO` (< 30), `OBESIDADE`.
- **ReferenceRange:** unidade, limites plausíveis (mínimo e máximo), faixa normal e limites críticos (cada lado pode ser vazio).
- **Classificação (`ResultFlag`):** `NORMAL`, `BAIXO`, `ALTO`, `CRITICO_BAIXO`, `CRITICO_ALTO`.
- **Laboratory:** `name`, `address`.
- **ExamType:** `code`, `name`, `category`, `sample_type`, `turnaround_hours`, `preparation`, lista de analitos (`code`, `name`, faixa de referência, `decimals`).
- **Categoria (`ExamCategory`):** `HEMATOLOGIA`, `BIOQUIMICA`, `HORMONIOS`, `VITAMINAS`.
- **Amostra (`SampleType`):** `SANGUE`, `URINA`, `OUTRO`.
- **ExamRequest:** `patient_id`, `exam_type_id`, `requested_by`, `appointment_id`, `laboratory_id`, `priority`, `clinical_indication` (até 500), `status`, `scheduled_for`, `sample_code`, `collected_at`, `results`, `result_notes` (até 2000), `validated_by`, `validated_at`, `released_at`, `cancellation_reason`, `history`.
- **Prioridade (`ExamPriority`):** `ROTINA` (padrão), `URGENTE`.
- **Estados (`ExamStatus`):** `SOLICITADO`, `AGENDADO`, `COLETADO`, `EM_PROCESSAMENTO`, `RESULTADO_REGISTRADO`, `VALIDADO`, `LIBERADO`, `CANCELADO`.
- **ExamResult:** `analyte_code`, `analyte_name`, `value`, `unit`, `reference_text`, `flag`. Unidade e referência são copiadas no registro.

### Catálogo de exames (`app/infrastructure/seed/lab_catalog.py`)

| Código | Exame | Analitos |
|---|---|---|
| `HEMO` | Hemograma | `HB`, `HT`, `LEUCO`, `PLAQ` |
| `GLI` | Glicemia de jejum | `GLI` |
| `HBA1C` | Hemoglobina glicada | `HBA1C` |
| `LIPID` | Perfil lipídico (colesterol) | `CT`, `HDL`, `LDL` |
| `TG` | Triglicerídeos | `TG` |
| `CREA` | Creatinina | `CREA` |
| `UREIA` | Ureia | `UREIA` |
| `K` | Potássio | `K` |
| `TSH` | TSH | `TSH` |
| `T4L` | T4 livre | `T4L` |
| `VITD` | Vitamina D (25-OH) | `VITD` |

Laboratórios: "Laboratório Central Fictício" e "Laboratório Exemplo Norte".

## Rotas (`/api/v1`)

- `POST /patients/{patient_id}/vital-signs`
- `GET /patients/{patient_id}/vital-signs` (filtros `date_from`, `date_to`; `limit` 1–200, padrão 20; `offset`)
- `GET /patients/{patient_id}/vital-signs/summary`
- `GET /exam-types`
- `GET /laboratories`
- `GET /exam-requests` (filtros `patient_id`, `status` repetível, `exam_type_id`, `priority`, `date_from`, `date_to`, `only_abnormal`, `newest_first`, `limit`, `offset`)
- `POST /exam-requests`
- `GET /exam-requests/{request_id}`
- `POST /exam-requests/{request_id}/schedule`
- `POST /exam-requests/{request_id}/collect`
- `POST /exam-requests/{request_id}/start-processing`
- `POST /exam-requests/{request_id}/results`
- `POST /exam-requests/{request_id}/validate`
- `POST /exam-requests/{request_id}/return`
- `POST /exam-requests/{request_id}/release`
- `POST /exam-requests/{request_id}/cancel`
- `GET /patients/{patient_id}/exams/analytes/{analyte_code}/history`

Interface: página `/app/laboratorio` e abas de sinais vitais e exames no prontuário (`static/js/pages/record-monitoring.js`).

## Critérios de aceitação

### Faixas de referência
- Valor fora dos limites plausíveis é recusado com 400 ("fora dos limites aceitáveis").
- Abaixo do crítico mínimo é `CRITICO_BAIXO`; acima do crítico máximo, `CRITICO_ALTO`.
- Abaixo da faixa normal é `BAIXO`; acima, `ALTO`; dentro, `NORMAL`.
- A descrição da faixa segue o formato "12–16 g/dL", "≥ 95 %" ou "≤ 189 mg/dL".

### Registro de sinais vitais
- É preciso informar ao menos uma medida. Corpo vazio retorna 400.
- A pressão exige sistólica e diastólica juntas, e a sistólica deve ser maior que a diastólica (400).
- Tipo inválido (ex.: texto em `heart_rate`) retorna 422.
- `recorded_at` é opcional (padrão: agora). Não pode estar no futuro nem antes do nascimento do paciente (400).
- Paciente ou profissional inexistente retorna 404.
- O registro criado retorna 201 com `flags` só das métricas que têm faixa normal (peso e altura não têm).
- O IMC é calculado com o peso do registro e a altura dele ou a última altura conhecida até aquela medição. É arredondado a uma casa e recebe `bmi_category`.

### Consulta de sinais vitais
- A listagem é paginada, com o registro mais recente primeiro.
- O resumo traz, por métrica, a última medida, a anterior, a tendência e a série temporal (até 30 registros).
- A tendência é `ESTAVEL` quando a variação relativa é de até 2%; senão `SUBINDO` ou `DESCENDO`. Com uma só medida, é vazia.
- O resumo inclui o aviso de que os valores são ilustrativos e educacionais.

### Catálogo
- Exames e laboratórios ausentes são cadastrados no startup da aplicação (por código e por nome), sem duplicar.
- Um tipo de exame precisa de pelo menos um analito, sem códigos repetidos.

### Ciclo do exame
- Transições permitidas:
  - `SOLICITADO` → `AGENDADO`, `COLETADO` ou `CANCELADO`.
  - `AGENDADO` → `AGENDADO` (reagendar), `COLETADO` ou `CANCELADO`.
  - `COLETADO` → `EM_PROCESSAMENTO`.
  - `EM_PROCESSAMENTO` → `RESULTADO_REGISTRADO`.
  - `RESULTADO_REGISTRADO` → `VALIDADO` ou `EM_PROCESSAMENTO` (devolução).
  - `VALIDADO` → `LIBERADO`.
  - `LIBERADO` e `CANCELADO` são finais.
- Transição não permitida retorna 409. Ex.: iniciar processamento sem coleta, liberar sem validar, cancelar após a coleta.
- Cada resposta traz `allowed_transitions` e o histórico de mudanças de estado.
- Solicitação inexistente retorna 404.

### Solicitação
- Paciente, tipo de exame ou laboratório inexistente retorna 404.
- Se informada, a consulta deve ser do paciente e não pode estar cancelada ou como falta (400).
- Sem `requested_by`, o solicitante é o profissional da consulta vinculada.

### Agendamento e coleta
- A coleta deve ser agendada para horário futuro (400).
- A coleta pode ocorrer direto da solicitação, sem agendamento.
- A coleta gera `sample_code` no formato `AM<AAAAMMDD>-<6 caracteres>`.
- `expected_by` é a hora da coleta mais o prazo do exame (`turnaround_hours`).

### Resultados
- Só é possível registrar resultados em `EM_PROCESSAMENTO` (409 fora dele).
- Faltar analito ou enviar analito que não pertence ao exame retorna 400.
- Valor fora dos limites plausíveis retorna 400, e o exame continua em processamento.
- Cada valor é arredondado às casas decimais do analito e classificado pela faixa.
- `has_abnormal_results` e `has_critical_results` indicam resultados fora da faixa e críticos.

### Validação, devolução, liberação e cancelamento
- Validar exige profissional existente (404) e ativo (400, "Somente profissionais ativos podem validar laudos.").
- Devolver exige motivo e descarta os resultados anteriores; o exame volta a `EM_PROCESSAMENTO`.
- Cancelar exige motivo, guardado em `cancellation_reason`.
- Motivo com menos de 3 caracteres é recusado com 422.

### Busca e histórico de analito
- `only_abnormal` lista só exames com algum resultado diferente de `NORMAL`.
- Valor de `status` fora do enum retorna 422.
- O histórico de um analito considera só exames `LIBERADO`, em ordem de coleta. O código é tratado sem diferenciar maiúsculas.

### Linha do tempo
- Sinais vitais e exames aparecem na linha do tempo do paciente. Registros com medida fora da referência aparecem como `ALTERADO`.

## Testes esperados

- Unidade: `tests/unit/test_vitals_and_laboratory_entities.py` (classificação das faixas, IMC, validações de sinais vitais, fluxo completo do exame, devolução, resultados inválidos, transições incoerentes, analitos únicos).
- Integração: `tests/integration/test_vitals_and_laboratory_use_cases.py` (IMC com última altura, tendências, validador ativo, histórico só de liberados, filtros de busca).
- API: `tests/api/test_vitals_and_laboratory_api.py` (catálogo no startup, sinais vitais via HTTP com 400 e 422, ciclo do exame com 409 e 400, 404 e 422, linha do tempo).
- Frontend: `tests/frontend/pages.smoke.mjs` e `tests/frontend/a11y.review.mjs` (página `/app/laboratorio`).

## Fora do escopo

- Faixas por sexo, idade ou método laboratorial.
- Interpretação clínica ou diagnóstico a partir dos resultados.
- Integração com equipamentos ou laboratórios reais.
- Cadastro de novos tipos de exame pela API.
