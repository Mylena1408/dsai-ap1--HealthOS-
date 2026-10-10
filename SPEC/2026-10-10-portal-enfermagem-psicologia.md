# Portal: visões de Enfermagem e Psicologia (2026-10-10)

## O quê e por quê

O portal (`/`), página que o usuário vê primeiro, só tinha as visões "Paciente" e "Médico". A equipe
de enfermagem e os psicólogos não tinham entrada própria, embora o sistema já registre sinais vitais,
procedimentos, evoluções, consultas e condições para qualquer profissional. Esta parte acrescenta as
visões **Enfermagem** (foco na equipe de enfermagem, não em leitos) e **Psicologia**, ligadas só às
rotas existentes.

Sem senha, login ou bloqueio (ADR-002). A visão Psicologia mostra um aviso didático de sigilo: em um
sistema real o registro psicológico tem acesso restrito; aqui ele é visível a qualquer perfil.

## Modelo de dados (resumo)

Sem tabelas e sem rotas novas. Frontend: `static/js/pages/portal-care.js` (visões novas),
`portal.js` (troca de visão), `index.html`, `role-nav.js`.

## Rotas (`/api/v1`) usadas (todas existentes)

- Enfermagem: `GET /appointments?date_from&date_to&status`, `POST /patients/{id}/vital-signs`,
  `POST /patients/{id}/procedures`, `POST /patients/{id}/evolutions`,
  `GET /alerts?rule_code=SINAL_VITAL_CRITICO&status`, `GET /patients/{id}/medications`.
- Psicologia: `GET /appointments?professional_id&date_from&date_to`,
  `POST /appointments/{id}/confirm|start|complete`, `GET /professionals/{id}/availability`,
  `POST /appointments`, `GET|POST /patients/{id}/evolutions`, `POST .../evolutions/{eid}/sign`,
  `GET|POST /patients/{id}/conditions`.
- Profissionais: `GET /professionals?status=ATIVO` (lista em cache).

## Critérios de aceitação

### Troca de visão
- Botões "Paciente", "Médico", "Enfermagem" e "Psicologia". Visão inicial pelo perfil: paciente →
  Paciente; enfermeiro ou setor Enfermagem → Enfermagem; psicólogo → Psicologia; outros
  profissionais → Médico; demais setores → Paciente.
- O paciente escolhido (por nome ou CPF) vale para todos os formulários de todas as visões.

### Enfermagem
- Pacientes do dia (consultas de hoje) com horário, profissional, situação e "Abrir prontuário".
- Registrar sinais vitais e procedimento com autor da equipe de enfermagem (sugerido pelo perfil).
- Evolução de enfermagem (rascunho; assinatura no prontuário).
- Sinais vitais críticos em aberto, com link para o prontuário.
- Medicamentos em uso do paciente escolhido (somente consulta).

### Psicologia
- Aviso: "Registro didático: em um sistema real o prontuário psicológico tem acesso restrito; aqui
  todos os dados são fictícios e visíveis a qualquer perfil."
- Minha agenda (hoje e próximos 7 dias) do psicólogo escolhido (sugerido pelo perfil), com
  Confirmar, Iniciar e Finalizar conforme a situação.
- Agendar sessão: horários livres do psicólogo, tipo (primeira consulta, retorno, teleconsulta).
- Registrar evolução da sessão e assiná-la (com confirmação).
- Histórico do paciente: evoluções e condições.
- Registrar queixa ou condição.

### Integração
- O que for gravado aparece no prontuário, na linha do tempo, no Painel e na auditoria pelas regras
  já existentes; sessão finalizada aparece em "não faturado".

## Testes esperados

- `npm run flow` (`care.flow.mjs`): enfermagem registra sinais vitais e procedimento (conferidos na
  API, autor e auditoria); psicologia agenda, inicia e finaliza sessão, registra e assina evolução
  (linha do tempo, "não faturado"), registra condição; visão inicial por perfil; aviso de sigilo.
- `npm run a11y` com as visões novas; `npm test`; `npm run smoke`; `pytest`.

## Fora do escopo

- Leitos e internação; escalas e testes psicológicos; controle de acesso; mudanças no back-end.
