# Eventos, auditoria, notificações internas e alertas por regra (2026-10-06)

## O quê e por quê

Auditoria e avisos precisam reagir a operações de vários módulos (consultas, exames, farmácia, financeiro). Chamar esses serviços dentro de cada caso de uso acoplaria todos os módulos entre si. Por isso os casos de uso publicam eventos de domínio, e manipuladores registrados gravam a trilha de auditoria e a caixa de notificações na mesma transação (ADR-016, ADR-017).

Além disso, situações de risco (estoque zerado, lote vencido, exame fora da referência, fatura vencida) precisam ser vistas sem que alguém procure por elas. Um motor de regras avalia os dados, abre alertas, agrava, e resolve sozinho quando a condição some (ADR-018).

## Modelo de dados (resumo)

Tabelas novas: `audit_events`, `inbox_notifications`, `system_alerts`. As tabelas legadas `audit_logs` e `notifications` não mudam.

- **DomainEvent:** `event_type`, `occurred_at`, `entity_type`, `entity_id`, `summary`, `patient_id`, `professional_id`, `data`.
- **Tipos de evento (`EventType`):** `PACIENTE_CRIADO`, `CONSULTA_AGENDADA`, `CONSULTA_CONFIRMADA`, `CONSULTA_REMARCADA`, `CONSULTA_CANCELADA`, `CONSULTA_FINALIZADA`, `CONSULTA_NAO_COMPARECEU`, `ALERGIA_REGISTRADA`, `DIAGNOSTICO_REGISTRADO`, `SINAIS_VITAIS_REGISTRADOS`, `EXAME_SOLICITADO`, `AMOSTRA_COLETADA`, `RESULTADO_REGISTRADO`, `RESULTADO_LIBERADO`, `EXAME_CANCELADO`, `PRESCRICAO_EMITIDA`, `PRESCRICAO_CANCELADA`, `MEDICAMENTO_DISPENSADO`, `ESTOQUE_ENTRADA`, `ESTOQUE_DESCARTE`, `ALERTA_GERADO`, `ALERTA_RESOLVIDO`, `ASSISTENTE_CONSULTADO`, `FATURA_EMITIDA`, `PAGAMENTO_REGISTRADO`, `FATURA_CANCELADA`, `RELATORIO_EXPORTADO`.
- **InboxNotification:** `audience`, `recipient_id` ou `sector`, `category`, `priority`, `title`, `message`, `link`, `source_event`, `status`, `created_at`, `read_at`, `archived_at`.
- **Público (`Audience`):** `PACIENTE`, `PROFISSIONAL`, `SETOR`.
- **Setores (`Sector`):** `RECEPCAO`, `LABORATORIO`, `FARMACIA`, `COORDENACAO_CLINICA`, `ADMINISTRACAO`.
- **Categorias (`NotificationCategory`):** `CONSULTA`, `EXAME`, `MEDICAMENTO`, `ALERTA`, `FINANCEIRO`, `ADMINISTRATIVO`.
- **Estados (`InboxStatus`):** `NAO_LIDA`, `LIDA`, `ARQUIVADA`. **Prioridade (`Priority`):** `NORMAL`, `ALTA`.
- **SystemAlert:** `rule_code`, `dedup_key`, `category`, `level`, `status`, `title`, `message`, `subject_type`, `subject_id`, `patient_id`, `link`, `first_detected_at`, `last_detected_at`, `acknowledged_at`, `acknowledged_by`, `resolved_at`, `resolution_note`, `auto_resolved`.
- **Categorias de alerta (`AlertCategory`):** `CLINICO`, `LABORATORIAL`, `MEDICAMENTO`, `CONSULTA`, `ESTOQUE`, `ADMINISTRATIVO`, `SISTEMA`.
- **Níveis (`AlertLevel`):** `INFO`, `ATENCAO`, `CRITICO`. **Estados (`SystemAlertStatus`):** `ATIVO`, `RECONHECIDO`, `RESOLVIDO`.

## Rotas (`/api/v1`)

- `GET /alerts/rules`
- `POST /alerts/evaluate` (corpo opcional `{"rules": [...]}`; padrão: todas)
- `GET /alerts` (filtros `status`, `category`, `level`, `patient_id`, `rule_code`, `limit`, `offset`)
- `GET /alerts/summary`
- `POST /alerts/{alert_id}/acknowledge`
- `POST /alerts/{alert_id}/resolve`
- `GET /inbox` (`audience` obrigatório; `recipient_id`, `sector`, `status`, `category`, `limit`, `offset`)
- `GET /inbox/counts`
- `POST /inbox/mark-all-read`
- `POST /inbox/{notification_id}/{action}` (`action` = `read`, `unread`, `archive` ou `unarchive`)
- `GET /audit-events` (filtros `event_type`, `entity_type`, `entity_id`, `patient_id`, `date_from`, `date_to`, `limit`, `offset`)
- `GET /audit-events/counts` (filtro `date_from`)

Páginas da interface: `/app/alertas`, `/app/notificacoes`, `/app/auditoria`.

## Critérios de aceitação

### Publicação de eventos
- Cada requisição usa um publicador próprio, ligado à mesma sessão do banco.
- O publicador entrega cada evento, em ordem, à trilha de auditoria e à política de notificações.
- Se a operação falhar, nada é gravado. Se um manipulador falhar, a operação é desfeita.
- Sem publicador configurado, os casos de uso usam `NullPublisher` e nada acontece.

### Auditoria
- Todo evento publicado vira um registro em `audit_events`, com o resumo legível do evento.
- A trilha é só leitura pela API. As contagens são agrupadas por tipo de evento.
- É rastreabilidade didática, não controle de segurança.

### Política de notificações
- `CONSULTA_AGENDADA`, `CONSULTA_REMARCADA` e `CONSULTA_CANCELADA` avisam o paciente e o profissional.
- `EXAME_SOLICITADO` avisa o setor `LABORATORIO`, com prioridade `ALTA` se o exame for urgente.
- `RESULTADO_LIBERADO` avisa o paciente e o profissional solicitante. Para o profissional, a prioridade é `ALTA` se houver resultado alterado.
- `PRESCRICAO_EMITIDA` avisa o setor `FARMACIA` e o paciente. `MEDICAMENTO_DISPENSADO` avisa o paciente.
- `FATURA_EMITIDA`, `PAGAMENTO_REGISTRADO` e `FATURA_CANCELADA` avisam o paciente (categoria `FINANCEIRO`).
- `ALERTA_GERADO` avisa o setor da regra (padrão `ADMINISTRACAO`). O título começa com "Novo alerta: " ou "Alerta agravado: ". Nível `CRITICO` gera prioridade `ALTA`.
- Se o destinatário do evento estiver vazio, aquela notificação pessoal é pulada.
- A mensagem é sempre o resumo do evento. Não há envio real de e-mail nem SMS.

### Caixa de notificações
- Notificação para setor exige o setor. Notificação pessoal exige o destinatário. O título é obrigatório.
- Consultar a caixa de um setor sem informar `sector`, ou de paciente/profissional sem `recipient_id`, retorna 400.
- Transições: `NAO_LIDA` ⇄ `LIDA`; qualquer estado não arquivado → `ARQUIVADA`; `unarchive` volta para `LIDA`.
- Arquivar marca também a data de leitura, se ainda não houver.
- Transição inválida retorna 409 (ex.: marcar como lida uma notificação já lida). Ação desconhecida retorna 422. Notificação inexistente retorna 404.
- `mark-all-read` devolve `{"updated": N}` com a quantidade alterada.
- As contagens trazem `unread`, `read` e `archived`.

### Regras de alerta (parâmetros didáticos)
- `ESTOQUE_BAIXO` (setor `FARMACIA`): quantidade menor ou igual ao mínimo; `CRITICO` se zerado, senão `ATENCAO`.
- `LOTE_VENCENDO` (setor `FARMACIA`): lote com saldo vencendo em até 30 dias; `CRITICO` se já vencido.
- `CONSULTA_PROXIMA_NAO_CONFIRMADA` (setor `RECEPCAO`): consulta agendada nas próximas 24 horas e não confirmada; nível `INFO`.
- `EXAME_FORA_REFERENCIA` (setor `COORDENACAO_CLINICA`): resultado liberado nos últimos 30 dias fora da referência; `CRITICO` se algum valor for crítico.
- `EXAME_ATRASADO` (setor `LABORATORIO`): exame coletado ou em processamento cujo prazo de resultado já passou; nível `ATENCAO`.
- `SINAL_VITAL_CRITICO` (setor `COORDENACAO_CLINICA`): a medição mais recente dos últimos 7 dias tem valor crítico. Uma nova medição normal resolve o alerta.
- `PACIENTE_SEM_ACOMPANHAMENTO` (setor `COORDENACAO_CLINICA`): condição ativa, sem consulta finalizada há mais de 180 dias e sem consulta futura; nível `INFO`.
- `FATURA_VENCIDA` (setor `ADMINISTRACAO`): fatura vencida com saldo em aberto; `CRITICO` após 30 dias.

### Motor de alertas
- Cada condição tem uma `dedup_key`. Reavaliar não abre alerta duplicado: atualiza o alerta aberto.
- Se o nível piorar, o alerta é agravado e publica `ALERTA_GERADO` de novo.
- Condição que deixa de ser detectada resolve o alerta automaticamente, com nota padrão e `auto_resolved = true`, e publica `ALERTA_RESOLVIDO`.
- Se a condição voltar depois de resolvida, um novo alerta é aberto.
- O relatório da avaliação traz `opened`, `refreshed`, `escalated`, `auto_resolved` e `by_rule`.
- Pedir uma regra desconhecida retorna 400.
- A avaliação também roda em segundo plano a cada `ALERT_EVALUATION_INTERVAL_MINUTES` (padrão 15). Valor 0 desliga o agendador.

### Operação manual de alertas
- Reconhecer só vale para alerta `ATIVO` e exige quem reconhece (mínimo de 3 caracteres).
- Resolver exige nota com pelo menos 5 caracteres (422 na API). Resolver alerta já resolvido retorna 409.
- Alerta inexistente retorna 404.
- O resumo traz os alertas abertos em `by_category` e `by_level`.

## Testes esperados

- Unidade: `tests/unit/test_engagement_domain.py` (ciclo da notificação, destino obrigatório, ciclo e agravamento do alerta, nota da resolução automática, roteamento da política, evento sem profissional).
- Integração: `tests/integration/test_alert_engine.py` (avaliação sem duplicar e com aviso ao setor, resolução automática, agravamento do lote ao vencer, reconhecer e resolver, regra desconhecida).
- API: `tests/api/test_engagement_api.py` (criação de paciente auditada, agendamento e liberação de exame notificam, ações e contagens da caixa, rotas de alertas).
- Frontend: `tests/frontend/pages.smoke.mjs` abre `/app/alertas`, `/app/notificacoes` e `/app/auditoria`.

## Fora do escopo

- Envio real de e-mail, SMS ou push.
- Fila ou broker de mensagens; eventos não são reprocessáveis.
- Agendador distribuído (com várias instâncias, a avaliação periódica deveria virar um job externo).
- Autenticação e controle de acesso na auditoria (ADR-002).
- Alteração das tabelas e rotas legadas de notificações (ver `2026-10-01-notificacoes.md`).
