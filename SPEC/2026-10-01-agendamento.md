# Agendamento por slots (2026-10-01)

## O quê e por quê

O médico (ou a recepção) cria horários de atendimento, e o paciente reserva um deles. O sistema não pode permitir dois horários sobrepostos para o mesmo profissional. O modelo é baseado em **slots**: cada slot é um intervalo de um médico, que está disponível, reservado, bloqueado ou cancelado.

## Modelo de dados (resumo)

- **Schedule (slot):** `doctor_id`, `start_time`, `end_time`, `status`, `patient_id` (preenchido quando reservado), `notes`.
- **Estados (`ScheduleStatus`):** `AVAILABLE`, `BOOKED`, `BLOCKED`, `CANCELED`.

## Regra de sobreposição

Dois intervalos A e B se sobrepõem quando `StartA < EndB` **e** `EndA > StartB`. Intervalos que apenas se tocam (fim de um igual ao início do outro) não se sobrepõem.

## Critérios de aceitação

### Criação de slot
- O início deve ser anterior ao fim.
- A duração mínima é 15 minutos e a máxima é 12 horas. Fora disso, o slot é recusado.
- O slot não pode se sobrepor a outro slot do **mesmo médico**. Em caso de conflito, a criação é recusada com mensagem que informa quantos slots conflitam.
- Slots que apenas se tocam nas pontas são permitidos.
- Slots de médicos diferentes podem ocupar o mesmo horário.
- Slots com status `CANCELED` não bloqueiam a criação de um novo slot no mesmo horário.

### Reserva
- Só um slot `AVAILABLE` pode ser reservado. A reserva muda o estado para `BOOKED` e grava o `patient_id`.
- Reservar um slot que não está disponível (`BOOKED`, `BLOCKED` ou `CANCELED`) é recusado com mensagem que mostra o estado atual.
- Reservar um slot inexistente retorna mensagem de não encontrado.
- Um paciente não pode reservar dois slots que se sobreponham.

### Cancelamento, bloqueio e liberação
- Um slot `AVAILABLE` não pode ser cancelado. Slots `BOOKED` podem.
- Cancelar muda o estado para `CANCELED`.
- Bloquear (licença, folga) muda o estado para `BLOCKED` e remove o `patient_id`.
- Liberar volta o slot para `AVAILABLE` e remove o `patient_id`.
- Toda mudança de estado atualiza `updated_at`.

### Consultas
- A agenda de um médico em um período lista os slots daquele médico dentro do intervalo, ordenados por início.
- Os agendamentos de um paciente listam os slots reservados por ele.
- A rota `GET /api/v1/clinical/patients/{id}/appointments` retorna os agendamentos do paciente.

### Rotas
- As operações de criar slot, reservar, cancelar, bloquear e consultar agenda estão expostas em um router de agendamento registrado em `main.py`, protegido por permissões.

### Auditoria
- Criação e mudanças de estado geram `AuditLog`.

## Testes esperados

- Unidade: validação de duração, transições de estado (reservar, cancelar, bloquear, liberar) com casos válidos e inválidos.
- Integração: criar slots que se sobrepõem, tocam e não se sobrepõem; reservar slot disponível e já reservado; cancelar e recriar no mesmo horário.

## Fora do escopo

- Lembretes automáticos de consulta (ver `notificacoes`).
- Agendamentos recorrentes.
- Remarcação em um passo.
- Fuso horário por unidade.
