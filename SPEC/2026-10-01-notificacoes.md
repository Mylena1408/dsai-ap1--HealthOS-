# Notificações (2026-10-01)

## O quê e por quê

A equipe e os pacientes precisam ser avisados sobre fatos que exigem atenção, como um paciente `RED` na triagem ou um lembrete de consulta. Esta parte cobre criação, prioridade, canal de envio e acompanhamento de leitura. O envio por SMS, e-mail e push é simulado, sem provedores externos.

## Modelo de dados (resumo)

- **Notification:** `user_id`, `patient_id` (opcional), `type`, `channel`, `title`, `message`, `priority`, `status`, `metadata`, `created_at`, `sent_at`, `read_at`.
- **Tipos (`NotificationType`):** `APPOINTMENT_REMINDER`, `CRITICAL_ALERT`, `BILLING_REMINDER`, `SYSTEM_UPDATE`, `TRIAGE_UPDATE`.
- **Canais (`NotificationChannel`):** `EMAIL`, `SMS`, `PUSH`, `IN_APP`.
- **Estados (`NotificationStatus`):** `PENDING`, `SENT`, `DELIVERED`, `FAILED`, `READ`.
- **Prioridade (inteiro):** 1 normal, 2 alta, 3 crítica.
- **`metadata`:** dicionário com ids de recursos para navegação direta (por exemplo, id da fatura ou da consulta).

## Rotas (`/api/v1/notifications`)

- `POST /send` (exige `notification:write`)
- `GET /me` (exige `notification:read`)
- `PATCH /{notification_id}/read`

## Critérios de aceitação

### Criação e envio
- Toda notificação exige destinatário, tipo, canal, título e mensagem não vazios.
- A prioridade só aceita os valores 1, 2 e 3.
- Uma notificação nasce em `PENDING`.
- Ao mudar o estado para `SENT`, a data `sent_at` é registrada.
- No canal `IN_APP`, a notificação é considerada enviada ao ser criada.
- Falha de envio muda o estado para `FAILED`.

### Eventos que geram notificação
- Triagem `RED` registrada: `notify_critical_triage` cria uma notificação do tipo `CRITICAL_ALERT`, prioridade 3, com o id do paciente e da triagem em `metadata`.
- Consulta agendada: `notify_appointment_reminder` cria um lembrete do tipo `APPOINTMENT_REMINDER` com o id do agendamento e a data em `metadata`.
- Estoque da farmácia em `ESTOQUE_BAIXO` ou `ESGOTADO`: notificação para a equipe de farmácia.
- A criação de notificações não pode impedir nem desfazer a operação de negócio que as originou.

### Leitura
- O usuário lista as próprias notificações com `GET /me`, ordenadas da maior prioridade para a menor e, dentro da mesma prioridade, da mais recente para a mais antiga.
- Marcar como lida muda o estado para `READ` e registra `read_at`. Marcar de novo não altera a data original.
- Um usuário só lê e marca as próprias notificações.

### Rastreabilidade
- Notificações guardam `created_at`, `sent_at` e `read_at`.
- Criação e mudanças de estado geram `AuditLog`.

## Testes esperados

- Unidade: `mark_as_read`, `update_status` (data de envio), validação de prioridade e de campos obrigatórios.
- Integração: triagem `RED` gerando notificação crítica, listagem em `GET /me` na ordem esperada, marcar como lida e isolamento entre usuários.

## Fora do escopo

- Provedores reais de SMS, e-mail e push.
- Preferências de notificação por usuário.
- Tempo real por WebSocket.
- Painéis de BI e relatórios gráficos.
