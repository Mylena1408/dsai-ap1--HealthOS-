# Financeiro ampliado (2026-10-06)

## O quê e por quê

O faturamento original (ver `2026-10-01-faturamento.md`) não registrava pagamentos, não listava faturas e tinha um estado `ATRASADO` que nada aplicava. Também não havia como saber se uma consulta ou um exame já tinha sido cobrado.

Esta parte amplia o faturamento sem alterar as tabelas `invoices` e `billing_items`: pagamentos parciais, cancelamento com motivo, faturamento direto de consultas e exames com tabela de preços fictícia, "em atraso" calculado pelo vencimento e indicadores do período (ADR-022). As rotas originais de `/billing` continuam iguais e usam as mesmas regras de domínio.

## Modelo de dados (resumo)

Tabelas novas (só referenciam `invoices`/`billing_items`):

- **`invoice_payments`:** `invoice_id`, `amount` (2 casas), `method`, `paid_at`, `note`. Só por acréscimo.
- **`invoice_cancellations`:** `invoice_id`, `reason`, `cancelled_at`.
- **`billing_item_sources`:** `item_id`, `source_type`, `source_id` (atendimento que originou o item). Sem restrição única.
- **`service_prices`:** `code` (único), `description`, `billing_type`, `price`, `active`.

Enums, com os valores aceitos pela API:

- **Estados (`BillingStatus`):** `RASCUNHO`, `PENDENTE`, `PARCIALMENTE_PAGO`, `PAGO`, `ATRASADO`, `CANCELADO`.
- **Tipos de cobrança (`BillingType`):** `CONSULTA`, `EXAME`, `PROCEDIMENTO`, `MEDICAMENTO`, `DIÁRIA_QUARTO`, `TAXA_URGENCIA`.
- **Formas de pagamento (`PaymentMethod`):** `PIX`, `CARTAO`, `DINHEIRO`, `CONVENIO`. `NAO_INFORMADO` existe só para pagamentos feitos pelo fluxo original, sem forma de pagamento.
- **Origem do item (`ServiceSource`):** `CONSULTA`, `EXAME`.

Valores em `Decimal` com duas casas. A API devolve os valores como texto (ex.: `"15.00"`).

## Rotas (`/api/v1`)

Novas:

- `GET /billing/invoices` (filtros `status`, `patient_id`, `start`, `end`, `number`, `limit`, `offset`)
- `GET /billing/invoices/{invoice_id}`
- `POST /billing/invoices/{invoice_id}/issue`
- `POST /billing/invoices/{invoice_id}/payments`
- `POST /billing/invoices/{invoice_id}/cancel`
- `GET /billing/patients/{patient_id}/unbilled`
- `POST /billing/patients/{patient_id}/invoices`
- `GET /billing/prices`
- `GET /billing/summary` (filtros `start`, `end`)

Originais, que continuam iguais: `POST /billing/invoices`, `POST /billing/invoices/{invoice_id}/charges`, `POST /billing/invoices/{invoice_id}/finalize`, `GET /billing/patients/{patient_id}/summary`.

Página da interface: `/app/financeiro`.

## Critérios de aceitação

### Ciclo da fatura
- Rascunho → Pendente (emissão) → Parcialmente paga → Paga. Rascunho ou fatura em aberto sem pagamento pode ser cancelada.
- Emitir exige fatura em `RASCUNHO` (409 em outro estado), pelo menos um item e total maior que zero (400).
- Na emissão, o vencimento é de 15 dias a partir da data de emissão.
- Itens só são adicionados em `RASCUNHO` (regra original).
- O detalhe informa `allowed_actions`: `emitir` e `cancelar` em rascunho; `pagar` e `cancelar` em aberto sem pagamento; só `pagar` em aberto com pagamento; nenhuma ação nos demais estados.

### Em atraso derivado
- `ATRASADO` não depende de processo que atualize o banco: fatura `PENDENTE` ou `PARCIALMENTE_PAGO` com vencimento já passado aparece como `ATRASADO`.
- O filtro `status=ATRASADO` usa a mesma regra na consulta SQL. Filtrar por `PENDENTE` ou `PARCIALMENTE_PAGO` exclui as vencidas.

### Pagamentos
- Só faturas em aberto (`PENDENTE`, `PARCIALMENTE_PAGO`, `ATRASADO`) recebem pagamento. Rascunho, paga ou cancelada retorna 409.
- O valor deve ser maior que zero (422 na API) e não pode passar do saldo em aberto (400).
- A forma de pagamento é obrigatória. `NAO_INFORMADO` é recusado (422).
- Saldo zerado muda para `PAGO`. Saldo restante muda para `PARCIALMENTE_PAGO`.
- O registro do pagamento retorna 201 com o detalhe atualizado.

### Cancelamento
- Exige motivo (mínimo de 3 caracteres; vazio retorna 422).
- Fatura `PAGO` ou `CANCELADO` não pode ser cancelada (409).
- Fatura com qualquer pagamento não pode ser cancelada (400): não há estorno.
- Depois de cancelada, emitir retorna 409.

### Faturar atendimentos
- "A faturar" lista consultas finalizadas e exames liberados do paciente que não estão em fatura não cancelada, com o preço da tabela.
- Paciente inexistente retorna 404.
- Criar fatura a partir de atendimentos aceita de 1 a 50 referências.
- Atendimento já faturado, inexistente ou de outro paciente retorna 409. O mesmo atendimento nunca entra em duas faturas ativas.
- Cancelar a fatura devolve o atendimento para "a faturar".
- Cobertura maior que 0 sem convênio informado retorna 400. A cobertura vai de 0 a 100.
- `issue` (padrão `true`) emite a fatura na criação. Com `false`, ela fica em `RASCUNHO`.
- O número segue o formato `FAT-AAAAMM-XXXXXX`.
- Serviço sem preço na tabela retorna 400. Exame sem preço próprio usa `EXAME-PADRAO`.

### Tabela de preços (fictícia)
- É garantida no startup: insere os códigos que faltam e não altera preços já cadastrados.
- Consultas: `CONSULTA-PRIMEIRA_CONSULTA` 250.00, `CONSULTA-RETORNO` 150.00, `CONSULTA-URGENCIA` 350.00 (`TAXA_URGENCIA`), `CONSULTA-TELECONSULTA` 120.00.
- Exames: `EXAME-HEMO` 35.00, `EXAME-GLI` 15.00, `EXAME-HBA1C` 40.00, `EXAME-LIPID` 55.00, `EXAME-TG` 18.00, `EXAME-CREA` 16.00, `EXAME-UREIA` 16.00, `EXAME-K` 18.00, `EXAME-TSH` 45.00, `EXAME-T4L` 45.00, `EXAME-VITD` 90.00, `EXAME-PADRAO` 30.00.
- Só preços ativos são listados.

### Convênio
- No detalhe, parte do convênio = total × cobertura ÷ 100, arredondada a 2 casas. Parte do paciente = total − parte do convênio.

### Listagem e indicadores
- Datas `start`/`end` são inclusivas. Data final anterior à inicial retorna 400 (na listagem e nos indicadores).
- O filtro `number` busca parte do número da fatura.
- Indicadores do período (padrão: mês corrente): faturado (sem canceladas), recebido, a receber (saldo de todas as faturas em aberto, de qualquer data), em atraso (valor e quantidade), faturas em aberto, faturas por estado, recebido por forma de pagamento e faturado por pagador (convênios e "Particular").
- A soma de "faturado por pagador" é igual ao faturado.
- A série mensal traz os últimos 6 meses até o fim do período.
- A resposta traz o aviso "Valores fictícios para demonstração."

### Eventos e alertas
- Emitir publica `FATURA_EMITIDA`. Pagar publica `PAGAMENTO_REGISTRADO`. Cancelar publica `FATURA_CANCELADA`.
- A regra `FATURA_VENCIDA` avisa a Administração e se resolve na próxima avaliação depois que a fatura é quitada (ver `2026-10-06-eventos-auditoria-notificacoes-alertas.md`).

### Erros gerais
- Fatura inexistente retorna 404.

## Testes esperados

- Unidade: `tests/unit/test_billing_entities.py` (emissão exige rascunho e total positivo, pagamento parcial e total, atraso derivado do vencimento, regras de cancelamento).
- Integração: `tests/integration/test_finance_use_case.py` (faturas de exemplo consistentes, nunca faturar duas vezes e cancelamento que libera, pagamentos, atraso, alerta e indicadores).
- API: `tests/api/test_finance_api.py` (tabela de preços, fatura a partir de atendimentos, pagamentos e listagem, cancelamento e 404, indicadores); `tests/api/test_existing_endpoints.py` (fluxo das rotas originais).
- Frontend: `tests/frontend/pages.smoke.mjs` abre `/app/financeiro`, o detalhe da fatura e o registro de pagamento.

## Fora do escopo

- Estorno e conciliação bancária.
- Nota fiscal e integração com operadoras.
- Juros, multa e parcelamento.
- Pagamento por meios reais.
- Alteração das tabelas e rotas originais do faturamento.
