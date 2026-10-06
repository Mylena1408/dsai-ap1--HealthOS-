# Prontuário eletrônico (2026-10-06)

## O quê e por quê

O profissional precisa encontrar o paciente e ver, num só lugar, o que importa antes do atendimento: alergias ativas, problemas em aberto, diagnósticos recentes e consultas. Esta parte cria um prontuário estruturado (perfil, contatos de emergência, alergias, condições, diagnósticos e procedimentos), uma busca paginada de pacientes e uma linha do tempo que reúne os eventos de todos os módulos.

Os dados são fictícios e didáticos. O resumo do prontuário traz um aviso de que as informações não substituem avaliação profissional.

## Modelo de dados (resumo)

Tabelas novas ligadas ao paciente legado: `patient_profiles` (1:1), `patient_emergency_contacts`, `patient_allergies`, `patient_conditions`, `patient_diagnoses`, `patient_procedures`.

- **PatientProfile:** `blood_type`, `occupation`, `notes`, `emergency_contacts`, `updated_at`.
- **Tipo sanguíneo (`BloodType`):** `A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-`, `NAO_INFORMADO` (padrão).
- **EmergencyContact:** `full_name`, `relationship`, `phone`, `is_primary`.
- **Allergy:** `substance`, `category`, `severity`, `reaction`, `status`, `recorded_at`, `resolved_at`.
  - `AllergyCategory`: `MEDICAMENTO`, `ALIMENTO`, `AMBIENTAL`, `OUTRO`.
  - `AllergySeverity`: `LEVE`, `MODERADA`, `GRAVE`.
  - `AllergyStatus`: `ATIVA`, `RESOLVIDA`.
- **Condition:** `name`, `code` (ilustrativo, ex.: CID-10), `status`, `onset_date`, `resolved_date`, `notes`, `recorded_at`.
  - `ConditionStatus`: `ATIVA`, `CONTROLADA`, `RESOLVIDA`.
- **Diagnosis:** `description`, `code`, `diagnosis_type`, `certainty`, `professional_id`, `appointment_id`, `notes`, `diagnosed_at`.
  - `DiagnosisType`: `PRINCIPAL` (padrão), `SECUNDARIO`.
  - `DiagnosisCertainty`: `SUSPEITA` (padrão), `CONFIRMADA`, `DESCARTADA`.
- **Procedure:** `name`, `performed_at`, `professional_id`, `appointment_id`, `notes`.
- **Evento da linha do tempo (somente leitura, `TimelineEventType`):** `CADASTRO`, `CONSULTA`, `NOTA_CLINICA`, `ALERTA`, `TRIAGEM`, `ALERGIA`, `CONDICAO`, `DIAGNOSTICO`, `PROCEDIMENTO`, `SINAIS_VITAIS`, `EXAME`, `PRESCRICAO`, `DISPENSACAO`. Campos: `occurred_at`, `event_type`, `title`, `description`, `status`, `source_id`.

## Rotas (`/api/v1`)

- `GET /patients` (parâmetros `q`, `order_by`, `limit`, `offset`)
- `GET /patients/{patient_id}/record`
- `GET /patients/{patient_id}/timeline` (parâmetros `types`, `date_from`, `date_to`, `newest_first`, `limit`, `offset`)
- `PUT /patients/{patient_id}/profile`
- `POST /patients/{patient_id}/emergency-contacts`
- `DELETE /patients/{patient_id}/emergency-contacts/{contact_id}`
- `GET /patients/{patient_id}/allergies` e `POST /patients/{patient_id}/allergies`
- `POST /patients/{patient_id}/allergies/{allergy_id}/resolve`
- `GET /patients/{patient_id}/conditions` e `POST /patients/{patient_id}/conditions`
- `PATCH /patients/{patient_id}/conditions/{condition_id}/status`
- `GET /patients/{patient_id}/diagnoses` e `POST /patients/{patient_id}/diagnoses`
- `POST /patients/{patient_id}/diagnoses/{diagnosis_id}/confirm`
- `POST /patients/{patient_id}/diagnoses/{diagnosis_id}/rule-out`
- `GET /patients/{patient_id}/procedures` e `POST /patients/{patient_id}/procedures`

Interface: `/app/prontuario` (aceita `?patient=<id>` para abrir um paciente direto).

## Critérios de aceitação

### Busca de pacientes
- O termo `q` (até 100 caracteres) procura no nome e no e-mail, sem diferenciar maiúsculas.
- Se o termo tiver dígitos, procura também no CPF usando só os dígitos (ex.: `714.287` encontra o CPF `71428793860`).
- `order_by` aceita `name` (padrão) ou `recent` (cadastro mais novo primeiro). Outro valor retorna 422.
- `limit` vai de 1 a 100 (padrão 20). `offset` começa em 0.
- A resposta é paginada (`items`, `total`, `limit`, `offset`). Cada item traz a idade calculada na data atual.

### Resumo do prontuário
- Retorna os dados do paciente, a idade, o perfil, as alergias `ATIVA`, as condições não resolvidas, os 5 diagnósticos mais recentes, até 5 próximas consultas ativas e a última consulta concluída.
- Sem perfil gravado, o resumo usa um perfil vazio com tipo sanguíneo `NAO_INFORMADO`.
- O campo `disclaimer` informa que os dados são fictícios e não substituem avaliação profissional.

### Paciente inexistente
- Resumo, linha do tempo e as listas de alergias, condições, diagnósticos e procedimentos de um paciente inexistente retornam 404.

### Perfil e contatos de emergência
- Tipo sanguíneo fora da lista retorna 422.
- São permitidos no máximo 3 contatos. O quarto é recusado com 400.
- O telefone do contato deve ter entre 10 e 13 dígitos. Fora disso, 400.
- Sempre existe exatamente um contato principal: o primeiro cadastrado ou o marcado com `is_primary`. Marcar um novo como principal desmarca os outros.
- Ao remover o principal, o primeiro contato restante passa a ser o principal.
- Remover um contato que não pertence ao paciente retorna 400.

### Alergias
- Não pode haver duas alergias `ATIVA` à mesma substância no mesmo paciente. A comparação ignora maiúsculas e espaços nas pontas. O caso repetido retorna 409.
- Depois de resolvida, a mesma substância pode ser registrada de novo.
- Resolver muda `ATIVA` para `RESOLVIDA` e grava `resolved_at`. Resolver de novo retorna 409.
- Resolver uma alergia que não existe ou é de outro paciente retorna 404.

### Condições
- Transições permitidas: `ATIVA → CONTROLADA`, `ATIVA → RESOLVIDA`, `CONTROLADA → ATIVA`, `CONTROLADA → RESOLVIDA` e `RESOLVIDA → ATIVA` (recidiva). Qualquer outra retorna 409.
- Ao resolver, `resolved_date` recebe a data atual. Na recidiva, `resolved_date` volta a vazio.
- O início não pode estar no futuro nem ser anterior ao nascimento do paciente (400).
- Condição inexistente ou de outro paciente retorna 404.

### Diagnósticos
- Somente diagnósticos `SUSPEITA` podem ser confirmados (`CONFIRMADA`) ou descartados (`DESCARTADA`). Tentar mudar outro estado retorna 409.
- Diagnóstico inexistente ou de outro paciente retorna 404.
- A resposta traz `professional_name` quando há profissional vinculado.

### Vínculo com consulta e profissional (diagnósticos e procedimentos)
- A consulta informada deve ser do mesmo paciente. Caso contrário, 400.
- Não é possível vincular a uma consulta cancelada ou com não comparecimento (400).
- Sem profissional informado, o registro herda o profissional da consulta.
- Profissional informado que não existe retorna 404.

### Procedimentos
- A data de realização não pode ser futura (400).
- O nome tem pelo menos 3 caracteres.

### Linha do tempo
- Reúne eventos de todas as fontes listadas em `TimelineEventType`.
- A ordem padrão é do mais recente para o mais antigo. `newest_first=false` inverte.
- `types` pode ser repetido para filtrar. Tipo inválido retorna 422.
- `date_from` posterior a `date_to` retorna 400.
- `limit` vai de 1 a 200 (padrão 50). A resposta é paginada com `total`.

### Validação de entrada
- Campos de texto respeitam os tamanhos dos DTOs (ex.: substância de 2 a 120 caracteres, descrição do diagnóstico de 3 a 500). Violações retornam 422.

## Testes esperados

- Unidade: `tests/unit/test_medical_record_entities.py` (contato principal e limite, telefone, resolução única de alergia, transições de condição, certeza do diagnóstico, procedimento no futuro).
- Integração: `tests/integration/test_medical_record_use_case.py` (busca, resumo consolidado, alergia duplicada, regras de condição, diagnóstico vinculado a consulta, linha do tempo ordenada e filtrada).
- API: `tests/api/test_medical_records_api.py` (busca paginada, CRUD via HTTP, linha do tempo, 404 para paciente inexistente).
- Frontend: `tests/frontend/pages.smoke.mjs` e `tests/frontend/a11y.review.mjs` abrem `/app/prontuario`.

## Fora do escopo

- Diagnóstico ou orientação médica real.
- Edição ou exclusão de alergias, condições, diagnósticos e procedimentos.
- Codificação oficial validada (o `code` é apenas ilustrativo).
- Autenticação e controle de acesso por perfil.
- Notas clínicas legadas (`/clinical/notes`), que apenas aparecem na linha do tempo.
