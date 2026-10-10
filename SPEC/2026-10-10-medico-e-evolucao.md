# Médico, evolução clínica e setor de enfermagem (2026-10-10)

## O quê e por quê

Fase 3 da modernização (`2026-10-10-modernizacao-visao-geral.md`). O prontuário não tinha onde
registrar a evolução clínica: as notas legadas (`/clinical/notes`) apontam para `users`, que o
sistema não cria para os profissionais, e só o portal as usava, com o ID digitado à mão. Esta parte:

- cria a **evolução clínica** em tabela nova ligada a `professionals` (D2), com aba no prontuário e
  entrada na linha do tempo;
- faz `/clinical/notes` aceitar o ID de um profissional, gravando como evolução, sem mudar caminho
  nem formato de resposta (ADR-001);
- acrescenta o **setor Enfermagem** à caixa de notificações;
- mostra ao médico uma **área com os IDs dos médicos disponíveis**;
- sugere o autor dos registros pelo perfil (R3), avisa quem não é médico na prescrição e liga a
  agenda do dia ao prontuário.

## Modelo de dados (resumo)

Tabela nova (ADR-003); nenhuma tabela existente muda.

- **`clinical_evolutions`**: `id`, `patient_id` (→ `patients`), `professional_id` (→ `professionals`,
  obrigatório), `appointment_id` (→ `appointments`, opcional), `content` (texto, 10 a 10.000
  caracteres), `status` (`RASCUNHO` | `ASSINADA`), `version` (começa em 1), `created_at`,
  `updated_at`, `signed_at`.
- Entidade `ClinicalEvolution` (`app/domain/entities/medical_record.py`): só o rascunho pode ser
  editado (cada edição soma 1 à versão); assinar fixa `signed_at` e torna o registro imutável.
- `Sector.NURSING = "ENFERMAGEM"` (`app/domain/entities/inbox.py`).
- `TimelineEventType.EVOLUTION = "EVOLUCAO"`; `EventType.EVOLUTION_SIGNED = "EVOLUCAO_ASSINADA"`.

## Rotas (`/api/v1`)

Novas:

- `GET /patients/{patient_id}/evolutions` — da mais recente para a mais antiga.
- `POST /patients/{patient_id}/evolutions` — cria rascunho `{ professional_id, content, appointment_id? }` (201).
- `PATCH /patients/{patient_id}/evolutions/{evolution_id}` — edita o rascunho `{ content }`.
- `POST /patients/{patient_id}/evolutions/{evolution_id}/sign` — assina.

Alteradas sem mudar caminho nem formato:

- `POST /clinical/notes`: se `doctor_id` for o ID de um profissional cadastrado, grava uma evolução
  e responde no formato da nota (`status` `DRAFT`/`FINALIZED`, `timestamp` = criação). Se não for,
  segue o comportamento legado (ID de usuário).
- `PATCH /clinical/notes/{id}` e `PATCH /clinical/notes/{id}/finalize`: procuram a nota legada e,
  se não existir, a evolução com o mesmo ID. Editar registro finalizado/assinado continua 400.
- `GET /clinical/patients/{patient_id}/history`: notas legadas e evoluções, da mais recente para a
  mais antiga.
- `GET /inbox?audience=SETOR&sector=ENFERMAGEM` passa a ser aceito.

## Critérios de aceitação

### Evolução clínica
- Criar exige paciente existente, profissional existente e texto com pelo menos 10 caracteres.
  Consulta, se informada, deve ser do paciente e não pode estar cancelada nem com falta.
- Editar rascunho soma 1 à versão; editar ou assinar evolução assinada responde 409.
- Assinar publica `EVOLUCAO_ASSINADA` (auditoria registra).
- Evolução de outro paciente responde 404.
- A linha do tempo mostra "Evolução clínica — <profissional>" na data da assinatura (ou da criação,
  no rascunho), com prévia do texto e situação; o filtro "Evolução" funciona.

### Aba "Evolução" no prontuário
- Lista as evoluções com data, profissional, tipo, versão e situação.
- Formulário com profissional (sugerido pelo perfil, se for profissional) e texto.
- Rascunho tem "Editar" e "Assinar"; assinar pede confirmação ("não poderá ser alterada").
- Botões ficam desativados durante o envio (evita registro duplicado).

### Setor Enfermagem
- Aparece no seletor de perfil e recebe "Nova prescrição para acompanhamento" a cada prescrição
  emitida (link para o prontuário do paciente).
- "Para você" do setor Enfermagem = sugestões do perfil Enfermeiro.

### Área de IDs dos médicos (Painel › Profissional)
- Quando o profissional escolhido é médico, o painel mostra "Médicos disponíveis": médicos ativos,
  com especialidade, registro e ID, e botão "Copiar ID".
- O portal (`index.html`) passa a indicar onde consultar o ID do médico.

### Autoria, prescrição e agenda
- Sinais vitais ("Registrado por") e exames ("Solicitado por") têm seletor de profissional,
  pré-preenchido pelo perfil quando ele é profissional; pode ficar em branco.
- Prescrição: o prescritor é pré-preenchido se o perfil for médico; perfil profissional de outro tipo
  vê o aviso "Apenas médicos(as) prescrevem".
- Agenda de hoje do Painel › Profissional: cada consulta tem "Abrir prontuário".

## Testes esperados

- Unidade: regras da `ClinicalEvolution`.
- Integração: criar, editar, assinar, imutabilidade, paciente errado, linha do tempo e auditoria.
- API: rotas novas; `/clinical/notes` com ID de profissional (criar, editar, finalizar, histórico)
  sem quebrar o teste legado; inbox do setor Enfermagem após prescrição.
- Frontend: `npm test` (setor Enfermagem nas sugestões); `npm run smoke` passa pela aba Evolução;
  `npm run a11y`.

## Fora do escopo

- Migrar notas legadas para a tabela nova.
- Assinatura digital real (a assinatura é só a mudança de situação, sem senha — ADR-002).
- Painel próprio da enfermagem (Fase 4).
