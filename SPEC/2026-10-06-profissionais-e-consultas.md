# Profissionais e consultas (2026-10-06)

## O quê e por quê

A agenda por slots (ver `agendamento`) não guardava quem é o profissional, em que departamento trabalha nem em que horários atende. Esta parte cadastra profissionais de saúde fictícios, com departamento, especialidade e grade semanal de atendimento.

Sobre esse cadastro funciona a consulta, com uma máquina de estados explícita. O sistema impede horários fora do expediente, conflitos de agenda e transições incoerentes, como iniciar uma consulta cancelada.

## Modelo de dados (resumo)

- **Department** (`departments`): `name` (mínimo de 3 caracteres), `description`.
- **Specialty** (`specialties`): `name` (mínimo de 3 caracteres), `description`, `default_duration_minutes` (padrão 30, entre 10 e 240).
- **Professional** (`professionals`): `full_name`, `professional_type`, `registry_number` (registro fictício, ex.: `CRM-PA 12345`), `department_id`, `specialty_id`, `email`, `phone`, `status`, `bio`, `working_hours`.
- **WorkingHours** (`professional_working_hours`): `weekday` (0 = segunda ... 6 = domingo), `start_time`, `end_time`.
- **Tipos (`ProfessionalType`):** `MEDICO`, `ENFERMEIRO`, `FARMACEUTICO`, `NUTRICIONISTA`, `FISIOTERAPEUTA`, `PSICOLOGO`, `OUTRO`.
- **Status do profissional (`ProfessionalStatus`):** `ATIVO`, `AFASTADO`, `INATIVO`.
- **Appointment** (`appointments`): `patient_id`, `professional_id`, `specialty_id`, `start_time`, `duration_minutes`, `appointment_type`, `status`, `reason`, `notes`, `cancellation_reason`. A resposta inclui `end_time`, `patient_name`, `professional_name`, `allowed_transitions` e `history`.
- **Histórico** (`appointment_status_history`): `from_status`, `to_status`, `changed_at`, `note`.
- **Tipos de consulta (`AppointmentType`):** `PRIMEIRA_CONSULTA` (padrão), `RETORNO`, `URGENCIA`, `TELECONSULTA`.
- **Estados (`AppointmentStatus`):** `AGENDADA`, `CONFIRMADA`, `EM_ANDAMENTO`, `FINALIZADA`, `CANCELADA`, `NAO_COMPARECEU`.

## Máquina de estados (`ALLOWED_TRANSITIONS`)

| De | Para |
| --- | --- |
| `AGENDADA` | `CONFIRMADA`, `CANCELADA`, `NAO_COMPARECEU` |
| `CONFIRMADA` | `EM_ANDAMENTO`, `CANCELADA`, `NAO_COMPARECEU` |
| `EM_ANDAMENTO` | `FINALIZADA` |
| `FINALIZADA`, `CANCELADA`, `NAO_COMPARECEU` | nenhuma (estados finais) |

Consultas `AGENDADA`, `CONFIRMADA` e `EM_ANDAMENTO` são ativas: ocupam a agenda do profissional e do paciente.

## Rotas (`/api/v1`)

- `GET /departments` e `POST /departments`
- `GET /specialties` e `POST /specialties`
- `GET /professionals` (filtros `q`, `professional_type`, `status`, `department_id`, `specialty_id`, `limit`, `offset`)
- `POST /professionals`
- `GET /professionals/{professional_id}`
- `PATCH /professionals/{professional_id}`
- `PUT /professionals/{professional_id}/working-hours`
- `GET /professionals/{professional_id}/availability` (`date_from`, `days`, `duration_minutes`)
- `GET /appointments` (filtros `patient_id`, `professional_id`, `status` repetível, `date_from`, `date_to`, `newest_first`, `limit`, `offset`)
- `POST /appointments`
- `GET /appointments/{appointment_id}`
- `POST /appointments/{appointment_id}/confirm`
- `POST /appointments/{appointment_id}/start`
- `POST /appointments/{appointment_id}/complete`
- `POST /appointments/{appointment_id}/cancel`
- `POST /appointments/{appointment_id}/no-show`
- `POST /appointments/{appointment_id}/reschedule`

Páginas da interface: `/app/profissionais` e `/app/consultas`.

## Critérios de aceitação

### Departamentos e especialidades
- Nome com menos de 3 caracteres é recusado com 422.
- Nome repetido, sem diferenciar maiúsculas de minúsculas, é recusado com 409.
- A duração padrão da especialidade fica entre 10 e 240 minutos.

### Profissionais
- O cadastro retorna 201, com `department_name` e `specialty_name` preenchidos.
- Registro profissional já cadastrado é recusado com 409.
- Tipo de profissional fora da lista é recusado com 422.
- Departamento ou especialidade inexistente retorna 404.
- Profissional inexistente retorna 404.
- A busca `q` procura trecho do nome ou do registro, sem diferenciar maiúsculas. O resultado é paginado e ordenado por nome.
- `limit` aceita de 1 a 100 (padrão 20).
- O `PATCH` altera só os campos enviados, inclusive o `status`.

### Grade de atendimento
- `PUT /professionals/{professional_id}/working-hours` substitui a grade inteira.
- Dia da semana fora de 0 a 6 é recusado.
- Início igual ou posterior ao fim é recusado com 400.
- Janelas sobrepostas no mesmo dia são recusadas com 400.

### Agendamento
- Paciente ou profissional inexistente retorna 404.
- Profissional `AFASTADO` ou `INATIVO` não aceita agendamento (400).
- O horário deve estar no futuro (400).
- Sem `duration_minutes`, vale a duração padrão da especialidade. Sem especialidade, 30 minutos.
- A duração deve ser múltipla de 5 e estar entre 10 e 240 minutos (400).
- Se o profissional tem grade, a consulta precisa caber inteira numa janela do mesmo dia (400, "fora do expediente").
- Sobreposição com consulta ativa do mesmo profissional é recusada com 409.
- Sobreposição com consulta ativa do mesmo paciente, com qualquer profissional, é recusada com 409.
- Consultas canceladas não bloqueiam o horário.
- A consulta nasce `AGENDADA`, com o primeiro registro no histórico.

### Transições
- Transição fora da tabela é recusada com 409 e o estado não muda.
- Cancelar exige motivo com pelo menos 3 caracteres (422 na API). Só é possível antes do horário marcado (400).
- Não comparecimento só pode ser registrado após o horário marcado (400).
- O atendimento só pode ser iniciado até 30 minutos antes do horário marcado (400).
- Finalizar aceita `notes` opcionais.
- Cada transição grava um registro no histórico.
- `allowed_transitions` lista só as transições possíveis no momento, considerando o relógio. Em estado final, a lista é vazia.

### Remarcação
- Só consultas `AGENDADA` ou `CONFIRMADA` podem ser remarcadas. Outros estados retornam 409.
- A nova data deve estar no futuro (400).
- A remarcação passa pelas mesmas checagens de expediente e conflito.
- A consulta volta a `AGENDADA` e o histórico registra a data anterior e a nova.

### Listagem e disponibilidade
- A listagem é paginada (`limit` de 1 a 200), ordenada por início. Com `newest_first`, as mais recentes vêm primeiro.
- `date_to` é inclusivo.
- Status inválido no filtro retorna 422.
- A disponibilidade gera horários dentro da grade, descontando consultas ativas e horários já passados.
- `days` aceita de 1 a 31 (422 fora disso). Sem `date_from`, começa hoje.
- Profissional que não está `ATIVO` não tem horários livres.

### Eventos
- Agendar, remarcar, confirmar, cancelar, finalizar e registrar não comparecimento publicam um evento de domínio da consulta.

## Testes esperados

- Unidade: `tests/unit/test_appointment_entity.py` (caminho feliz, transições incoerentes, regras de horário, motivo do cancelamento, remarcação, durações inválidas, grade de atendimento).
- Integração: `tests/integration/test_appointment_use_case.py` (ciclo completo, regras de agendamento, horário cancelado reaproveitado, conflitos na remarcação, não comparecimento, disponibilidade, profissional afastado, busca, registro e nomes duplicados).
- API: `tests/api/test_professionals_and_appointments_api.py` (cadastro e busca, grade, ciclo de vida por HTTP, filtros e disponibilidade, paciente inexistente).
- Frontend: `tests/frontend/pages.smoke.mjs` (páginas `/app/consultas` e `/app/profissionais`).

## Fora do escopo

- Histórico de atividades do profissional (`/professionals/{id}/activity`).
- Autenticação e permissões nestas rotas.
- Consultas recorrentes.
- Fuso horário por unidade.
- Registro real em conselho de classe.
