# Estabilização dos endpoints existentes (2026-10-06)

## O quê e por quê

Antes da expansão, vários fluxos que já existiam respondiam com erro 500: adicionar estoque pela segunda vez, dispensar, lançar cobrança, finalizar fatura, ver o resumo financeiro e listar usuários. Erros de domínio também viravam 500 em alguns routers, e o portal colocava dados da API direto em `innerHTML`.

Esta parte corrige esses pontos sem mudar contratos. O objetivo é ter uma base estável, coberta por testes de regressão, antes de acrescentar módulos novos.

## Modelo de dados (resumo)

- Nenhuma tabela nova. As correções ficam nos repositórios, nos routers, no DTO de usuário e no startup.
- **Médico de demonstração:** e-mail `medico.demo@healthos.local`, CPF fictício `11144477735` (dígitos verificadores válidos, constante `DEMO_DOCTOR_CPF` em `main.py`).
- **`UserResponseDTO.email`:** passa a ser `str`, e não `EmailStr`. A resposta apenas devolve o que está gravado, e o usuário de demonstração usa o domínio reservado `.local`.

## Rotas (`/api/v1`)

Nenhuma rota nova. Os fluxos estabilizados e cobertos por regressão são:

- Pacientes: `POST /admin/patients/`, `GET /admin/patients/`, `GET /admin/patients/{patient_id}`, `PATCH /admin/patients/{patient_id}`
- Usuários: `GET /admin/users/`
- Agendamento: `GET /clinical/availability`, `POST /clinical/schedule`, `GET /clinical/patients/{patient_id}/appointments`
- Notas clínicas: `POST /clinical/notes`, `PATCH /clinical/notes/{note_id}`, `PATCH /clinical/notes/{note_id}/finalize`, `GET /clinical/patients/{patient_id}/history`
- Alertas: `POST /admin/alerts/`, `GET /admin/alerts/patient/{patient_id}/active`
- Farmácia: `POST /pharmacy/medications`, `POST /pharmacy/inventory/{medication_id}/{location_id}`, `POST /pharmacy/dispense/{medication_id}/{location_id}`, `GET /pharmacy/critical-stock`
- Faturamento: `POST /billing/invoices`, `POST /billing/invoices/{invoice_id}/charges`, `POST /billing/invoices/{invoice_id}/finalize`, `GET /billing/patients/{patient_id}/summary`
- Notificações: `POST /notifications/send`, `GET /notifications/me`, `PATCH /notifications/{notification_id}/read`

Fora de `/api/v1`: `GET /` (portal) e `GET /openapi.json` respondem 200.

## Critérios de aceitação

### Erros de domínio
- Os routers de usuários, alertas, notificações e autenticação importam `DomainException`. Um erro de domínio não vira mais 500.
- Nesses routers, erro de domínio responde 400. Na autenticação, responde 401.

### Pacientes
- Cadastrar um CPF já existente responde 400 ("Paciente com CPF ... já cadastrado.").
- CPF inválido (ex.: `11111111111`) responde 400.
- `PATCH` atualiza o telefone e devolve o valor novo.
- Paciente inexistente responde 404.

### Usuários e médico de demonstração
- `GET /admin/users/` responde 200 e inclui `medico.demo@healthos.local`.
- No startup, o médico de demonstração é criado com o CPF `11144477735`.
- Bancos antigos em que o médico tinha CPF `99999999999` são corrigidos no startup para o CPF válido.
- O startup cria horários de demonstração (seg. a sex., próximos 14 dias, 9h, 10h, 11h, 14h, 15h e 16h, 30 minutos cada), sem duplicar os já existentes.

### Agendamento e notas clínicas
- Reservar um horário disponível responde 201 com status `BOOKED`. Reservar o mesmo horário de novo responde 400.
- Editar uma nota em rascunho incrementa a versão (passa a 2).
- Depois de finalizada (`FINALIZED`), editar a nota responde 400.
- A nota aparece no histórico do paciente.

### Farmácia (estoque)
- Adicionar estoque a um item que já existe atualiza o registro, em vez de inserir outro com a mesma chave. Ex.: 12 + 3 resulta em 15.
- Dispensar reduz o estoque e responde 200. Ex.: 15 − 6 resulta em 9.
- Dispensar mais do que o disponível responde 400.
- O item com quantidade baixa aparece em `GET /pharmacy/critical-stock`.

### Faturamento
- Salvar uma fatura existente atualiza o registro e só acrescenta os itens novos.
- Os itens da fatura são carregados junto com ela (sem lazy loading em sessão assíncrona).
- Finalizar uma fatura sem itens responde 400.
- Lançar cobrança responde 200. Finalizar com itens leva ao status `PENDENTE`.
- Com cobertura de 80% sobre R$ 200, o resumo do paciente mostra `patient_share` igual a 40.

### Triagem
- Com várias triagens do mesmo paciente, a busca devolve a mais recente (ordem por `created_at`, limite 1), sem erro.

### Notificações
- Enviar responde 201, e a notificação aparece em `GET /notifications/me`.
- Depois de marcada como lida, ela some da lista de não lidas.
- Enviar sem destinatário responde 400.

### Portal (XSS)
- Dados vindos da API são escapados (`escapeHtml`) antes de entrar em `innerHTML`: status da consulta, número e status do débito, status e conteúdo da nota.
- A data da nota no portal usa o campo `timestamp`.

### Suíte de testes
- `tests/conftest.py` aponta `DATABASE_URL` para um SQLite temporário antes de importar a aplicação. Os testes nunca tocam no `app.db` da demonstração.
- A fixture `db_session` usa SQLite em memória, recriado a cada teste.
- `pytest.ini` define `testpaths = tests` e `asyncio_mode = auto`.
- As dependências de teste ficam em `requirements-dev.txt` (inclui `requirements.txt`, `pytest`, `pytest-asyncio`, `httpx`).

## Testes esperados

- API: `tests/api/test_existing_endpoints.py` (portal e docs, CRUD de pacientes, CPF inválido, listagem de usuários com o médico de demonstração, reserva, imutabilidade da nota, alertas, estoque e dispensação, faturamento, notificações).
- Integração: `tests/integration/test_patient_journey.py` (paciente, triagem, agendamento, farmácia e faturamento em sequência, com dados fictícios).

## Fora do escopo

- Novas rotas ou mudanças de contrato nos endpoints existentes.
- Autenticação real (a demonstração segue sem login).
- Revisão de todos os campos `innerHTML` das páginas novas (ver `observabilidade-e-frontend`).
