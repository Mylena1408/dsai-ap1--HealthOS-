# Faturamento e convênios (2026-10-01)

## O quê e por quê

Cada atendimento gera uma cobrança. Quando o paciente tem convênio, o hospital cobra do plano a parte coberta e do paciente a coparticipação. Erros de arredondamento ou de estado em valores financeiros geram prejuízo, então todos os cálculos usam `Decimal` e o ciclo de vida da fatura é controlado.

## Modelo de dados (resumo)

- **Invoice:** `patient_id`, `invoice_number`, `issue_date`, `due_date`, `status`, itens, `insurance_provider`, `insurance_policy_number`, `insurance_coverage_percentage`.
- **BillingItem:** `description`, `billing_type`, `quantity` (`Decimal`), `unit_price` (`Decimal`), `discount` (`Decimal`).
- **Tipos (`BillingType`):** `CONSULTATION`, `EXAM`, `PROCEDURE`, `MEDICATION`, `ROOM_STAY`, `URGENCY_FEE`.
- **Estados (`BillingStatus`):** `DRAFT`, `PENDING`, `PAID`, `PARTIALLY_PAID`, `OVERDUE`, `CANCELLED`. O ciclo principal é `DRAFT`, `PENDING`, `PAID`.

## Regras de cálculo

- Total do item = (quantidade × preço unitário) − desconto.
- Total bruto da fatura = soma dos totais dos itens.
- O percentual de cobertura é informado de 0 a 100 (80.00 significa 80%).
- Parte do paciente (coparticipação) = total bruto × (1 − percentual / 100), arredondada a 2 casas decimais (`ROUND_HALF_UP`).
- Parte do convênio = total bruto − parte do paciente. A soma das duas partes é sempre igual ao total bruto.
- Paciente sem convênio paga 100% do total bruto.

## Rotas (`/api/v1/billing`)

- `POST /invoices`
- `POST /invoices/{invoice_id}/charges`
- `POST /invoices/{invoice_id}/finalize`
- `POST /invoices/{invoice_id}/pay`
- `GET /patients/{patient_id}/summary`

## Critérios de aceitação

### Itens
- Quantidade deve ser maior que 0 e preço unitário maior ou igual a 0.
- O desconto não pode ser negativo nem maior que (quantidade × preço unitário).
- Nenhum cálculo usa `float`.

### Ciclo de vida
- A fatura nasce em `DRAFT`. Só nesse estado é possível adicionar itens. Tentar adicionar em outro estado é recusado com mensagem clara.
- `finalize` exige pelo menos um item, muda o estado para `PENDING` e define o vencimento em 15 dias a partir da emissão.
- `pay` só é permitido para fatura `PENDING` e muda para `PAID`. Pagar fatura `DRAFT` ou já paga é recusado.
- Uma fatura `PAID` não muda mais de estado.

### Convênio e coparticipação
- O percentual de cobertura deve estar entre 0 e 100, inclusive.
- Exemplo verificável: itens somando R$ 265,00 com cobertura de 80% resultam em coparticipação de R$ 53,00 e parte do convênio de R$ 212,00.
- Exemplo de arredondamento: total R$ 100,01 com cobertura de 50% resulta em coparticipação de R$ 50,01 (arredondado a 2 casas) e parte do convênio de R$ 50,00. A soma é R$ 100,01.

### Resumo financeiro
- O resumo por paciente lista, para cada fatura: número, total bruto, parte do paciente, estado e vencimento.

### Permissões
- Criar fatura, adicionar item, finalizar e pagar exigem `billing:write`. Consultar o resumo exige `billing:read`.

### Auditoria
- Criação, itens e mudanças de estado geram `AuditLog`.

## Testes esperados

- Unidade: cálculo de item e de total, coparticipação com os dois exemplos acima, regras de estado (adicionar item fora de `DRAFT`, finalizar sem itens, pagar fatura `DRAFT`).
- Integração: criar fatura, adicionar itens, finalizar, pagar e consultar o resumo, como no fluxo de jornada do paciente.

## Fora do escopo

- Nota fiscal.
- Integração com operadoras (autorização, glosa).
- Parcelamento, juros, multa e os estados `PARTIALLY_PAID`, `OVERDUE` e `CANCELLED` como transições automáticas (existem no enum, mas não têm regra nesta versão).
- Pagamento por meios reais.
