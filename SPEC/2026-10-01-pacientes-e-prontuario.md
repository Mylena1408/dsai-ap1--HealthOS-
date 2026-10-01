# Pacientes, alertas e prontuário eletrônico (2026-10-01)

## O quê e por quê

O hospital precisa de um cadastro confiável de pacientes, de alertas críticos visíveis (como alergias) e de um histórico clínico que não possa ser adulterado depois de finalizado, como exigem os registros médicos.

## Modelo de dados (resumo)

- **Patient:** `full_name`, `birth_date`, `cpf` (único), `gender`, `insurance_provider`, `insurance_number`, `phone`, `email`, `address`.
- **PatientAlert:** `patient_id`, `alert_type` (`ALLERGY`, `CHRONIC_CONDITION`, `RISK_FACTOR`, `OTHER`), `severity` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), `description`, `is_active`.
- **ClinicalNote:** `patient_id`, `doctor_id`, `content`, `timestamp`, `status` (`DRAFT` ou `FINALIZED`), `version`.

## Rotas

- Pacientes (`/api/v1/admin/patients`): `POST /`, `GET /`, `GET /{id}`, `PATCH /{id}`.
- Alertas (`/api/v1/admin/alerts`): `POST /`, `GET /patient/{patient_id}/active`.
- Prontuário (`/api/v1/clinical`): `POST /notes`, `PATCH /notes/{id}`, `PATCH /notes/{id}/finalize`, `GET /patients/{id}/history`, `GET /patients/{id}/appointments`.

## Critérios de aceitação

### Cadastro de paciente
- Nome, data de nascimento, CPF e gênero são obrigatórios.
- O CPF deve ter 11 dígitos numéricos (pontuação é ignorada) e não pode ter todos os dígitos iguais. CPF inválido é recusado.
- O CPF é único. Cadastrar o mesmo CPF duas vezes retorna conflito, não erro 500.
- A data de nascimento não pode estar no futuro.
- Criar e listar exigem `patient:write` e `patient:read`. Atualizar exige `patient:update`.
- A atualização de contato (`phone`, `email`) só altera os campos informados.

### Alertas do paciente
- A descrição do alerta tem no mínimo 3 caracteres.
- É possível ativar e desativar um alerta. A rota de alertas ativos retorna só os alertas com `is_active = true` do paciente.
- Alertas de severidade `CRITICAL` aparecem primeiro na listagem.

### Notas clínicas
- Uma nota nasce em `DRAFT`, com `version` 1.
- Editar o conteúdo de uma nota `DRAFT` incrementa a `version` em 1.
- Finalizar muda o estado para `FINALIZED`. A transição é irreversível.
- Nota `FINALIZED` não pode ser editada nem finalizada de novo. A tentativa retorna erro de domínio (`NoteImmutableError`) com resposta HTTP 4xx e nada é alterado.
- Criar e editar exigem `clinical:write`. Consultar o histórico exige `clinical:read`.
- A nota não pode ter conteúdo vazio.

### Evolução clínica
- O histórico do paciente lista as notas em ordem cronológica, da mais recente para a mais antiga.
- Cada item mostra médico, data, estado e versão.

### Auditoria
- Criação e alteração de pacientes, alertas e notas geram `AuditLog` (ver `usuarios-e-auth`).

## Testes esperados

- Unidade: validação de `Patient` (CPF e data), validação de `PatientAlert`, máquina de estados da nota (editar em `DRAFT`, finalizar, editar após finalizar, finalizar duas vezes).
- Integração: cadastro com CPF duplicado, listagem de alertas ativos, fluxo criar, editar, finalizar e tentar editar nota, histórico em ordem.

## Fora do escopo

- Validação dos dígitos verificadores do CPF.
- Anexo de exames e imagens.
- Prescrição eletrônica assinada digitalmente.
- Criação de nota corretiva vinculada a uma nota finalizada.
