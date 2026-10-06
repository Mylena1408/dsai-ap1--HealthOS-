# Farmácia: prescrição, lotes e dispensação FEFO (2026-10-06)

## O quê e por quê

A primeira versão da farmácia (ver `2026-10-01-farmacia.md`) guardava só um total por medicamento e local, sem lote, sem validade por lote e sem receita. Isso não permite saber qual lote saiu, nem impede que um lote vencido seja entregue ao paciente.

Esta parte é a evolução: lotes com validade, saída FEFO (o que vence primeiro sai primeiro), trilha de movimentações, prescrição feita por médico e dispensação feita por farmacêutico, com checagem didática de alergia. As rotas legadas de `/api/v1/pharmacy/...` continuam iguais (ADR-014).

## Modelo de dados (resumo)

Tabelas novas: `medication_categories`, `medication_details`, `stock_lots`, `inventory_movements`, `prescriptions`, `prescription_items`, `dispensations`, `dispensation_lines`.

- **MedicationCategory:** `name` (mínimo de 3 caracteres), `description`.
- **MedicationDetails** (1:1 com o medicamento legado): `category_id`, `catalog_status`, `requires_prescription` (padrão `true`).
- **Situação no catálogo (`CatalogStatus`):** `ATIVO`, `DESCONTINUADO`.
- **StockLot:** `medication_id`, `location`, `lot_number`, `expiration_date`, `quantity`, `received_at`.
- **InventoryMovement:** `medication_id`, `location`, `movement_type`, `quantity` (sempre positiva), `balance_after`, `lot_id`, `reference_id`, `reason`, `occurred_at`.
- **Tipos de movimentação (`MovementType`):** `ENTRADA`, `DISPENSACAO`, `AJUSTE`, `DESCARTE`.
- **Prescription:** `patient_id`, `prescriber_id`, `appointment_id`, `issued_at`, `items`, `notes`, `special_control`, `allergy_override_reason`, `status`, `cancellation_reason`. A resposta traz também `valid_until` e `is_expired`.
- **Estados da prescrição (`PrescriptionStatus`):** `ATIVA`, `PARCIALMENTE_DISPENSADA`, `DISPENSADA`, `CANCELADA`.
- **PrescriptionItem:** `medication_id`, `dose`, `frequency`, `duration_days`, `quantity`, `route`, `instructions`, `dispensed_quantity`, `status`, `status_reason`. A resposta traz `remaining_quantity`.
- **Vias (`AdministrationRoute`):** `ORAL` (padrão), `SUBLINGUAL`, `TOPICA`, `INALATORIA`, `INTRAVENOSA`, `INTRAMUSCULAR`, `SUBCUTANEA`.
- **Estados do item (`ItemStatus`):** `EM_USO`, `SUSPENSO`, `CONCLUIDO`.
- **Dispensation:** `prescription_id`, `patient_id`, `pharmacist_id`, `location`, `dispensed_at`, `notes`, `lines` (uma linha por lote usado: `lot_id`, `lot_number`, `quantity`; lote vazio = estoque sem lote).

## Rotas (`/api/v1`)

- `GET /medication-categories`
- `POST /medication-categories`
- `GET /medications/stock` (filtros `q`, `category_id`, `low_stock_only`)
- `PUT /medications/{medication_id}/details`
- `GET /stock/lots` (filtros `medication_id`, `location`, `expiring_within_days`, `include_empty`, `limit`, `offset`)
- `POST /stock/lots`
- `POST /stock/lots/{lot_id}/discard`
- `GET /stock/movements` (filtros `medication_id`, `location`, `movement_type`, `reference_id`, `date_from`, `date_to`, `limit`, `offset`)
- `POST /prescriptions`
- `GET /prescriptions` (filtros `patient_id`, `prescriber_id`, `status`, `limit`, `offset`)
- `GET /prescriptions/{prescription_id}`
- `POST /prescriptions/{prescription_id}/cancel`
- `POST /prescriptions/{prescription_id}/items/{item_id}/{action}` (`action` = `suspend`, `resume` ou `complete`)
- `POST /dispensations`
- `GET /dispensations` (filtros `prescription_id`, `patient_id`, `limit`, `offset`)
- `GET /patients/{patient_id}/medications` (filtro `status`)

Página da interface: `/app/farmacia`.

## Critérios de aceitação

### Catálogo complementar
- Criar categoria com nome já existente retorna 409.
- Definir detalhes de medicamento inexistente retorna 404. Categoria inexistente também retorna 404.
- A posição de estoque mostra, por medicamento, total, quantidade em lotes, quantidade sem lote, locais abaixo do mínimo e validade mais próxima.
- `low_stock_only=true` mantém só medicamentos com ao menos um local com quantidade menor ou igual ao mínimo.

### Lotes e coerência com o legado
- O total legado (`inventory_items`) continua sendo a fonte da verdade. A diferença entre o total e a soma dos lotes é "estoque sem lote".
- Receber lote soma a quantidade ao total legado e registra uma movimentação `ENTRADA`.
- O total legado guarda a validade mais próxima entre os lotes recebidos.
- O número do lote é normalizado (sem espaços nas pontas, em maiúsculas). O local também é gravado em maiúsculas.
- Receber de novo o mesmo lote no mesmo local retorna 409.
- Receber lote já vencido (validade até hoje) retorna 400.
- Quantidade 0 no recebimento retorna 422.
- Medicamento `DESCONTINUADO` não recebe lote novo (400).
- Toda operação nova começa reconciliando: se a soma dos lotes passar do total legado (saída feita pela rota legada), o excesso é baixado dos lotes por validade e registrado como `AJUSTE`.
- `expiring_within_days` inclui lotes já vencidos. Por padrão, lotes zerados não aparecem.

### Descarte
- Lote vencido pode ser descartado sem justificativa.
- Lote dentro da validade exige justificativa com pelo menos 10 caracteres (400).
- Lote sem saldo não pode ser descartado (400). Lote inexistente retorna 404.
- O descarte zera o lote, baixa o total legado e registra `DESCARTE`.

### Prescrição
- Só médicos ativos prescrevem. Outro tipo de profissional retorna 400. Paciente ou profissional inexistente retorna 404.
- A consulta vinculada (opcional) deve ser do paciente e não pode estar cancelada nem marcada como falta (400).
- Pelo menos 1 item e no máximo 20. Lista vazia retorna 422.
- O mesmo medicamento não pode aparecer duas vezes (400).
- `duration_days` entre 1 e 365. Quantidade maior que 0 e no máximo 1000.
- Medicamento `DESCONTINUADO` não pode ser prescrito (400).
- Substância controlada: no máximo 60 unidades por receita (400). A prescrição com controlada sai com `special_control = true`.
- Alergia ativa cujo texto coincide com o nome ou o princípio ativo bloqueia a prescrição com 409. A mensagem lista os pares "medicamento × substância".
- Com `allergy_override_reason` de pelo menos 10 caracteres, a prescrição é aceita e a justificativa fica registrada.
- A validade da prescrição é de 30 dias a partir da emissão.

### Itens e cancelamento
- `suspend` exige motivo (mínimo de 3 caracteres) e só vale para item `EM_USO`.
- `resume` só vale para item `SUSPENSO`. `complete` só vale para item `EM_USO`.
- Transição inválida retorna 409 (ex.: suspender item já suspenso). Ação fora das três aceitas retorna 422.
- Cancelar exige motivo e não é permitido para prescrição `DISPENSADA` ou `CANCELADA` (409).
- Prescrição inexistente retorna 404. Item que não pertence à prescrição retorna 400.

### Dispensação
- Só farmacêuticos ativos dispensam (400).
- Só prescrições `ATIVA` ou `PARCIALMENTE_DISPENSADA` são dispensáveis (409). Prescrição vencida retorna 400.
- Cada item aparece uma única vez. Só itens `EM_USO` são dispensados. Quantidade acima do saldo retorna 400 ("restam N").
- Tudo é validado antes de mexer no estoque.
- A baixa segue FEFO: lotes válidos do vencimento mais próximo ao mais distante, estoque sem lote por último. Lotes vencidos nunca são usados.
- Estoque válido insuficiente retorna 409 ("Estoque válido insuficiente").
- Cada parte da baixa gera movimentação `DISPENSACAO` com `reference_id` = id da dispensação.
- Depois da dispensação, o estado da prescrição é recalculado: `DISPENSADA` quando nenhum item em uso tem saldo; `PARCIALMENTE_DISPENSADA` quando algo já saiu.

### Medicamentos do paciente
- Lista os itens de prescrições não canceladas, com filtro opcional por `status`. Paciente inexistente retorna 404.

### Eventos
- Prescrição emitida, prescrição cancelada, dispensação, entrada de lote e descarte publicam eventos de domínio (ver `2026-10-06-eventos-auditoria-notificacoes-alertas.md`).

## Testes esperados

- Unidade: `tests/unit/test_pharmacy_entities.py` (FEFO, lote vencido, normalização do lote, estados da prescrição, itens suspensos, validade, cancelamento).
- Integração: `tests/integration/test_pharmacy_use_cases.py` (recebimento e total legado, fluxo completo com FEFO, reconciliação com a rota legada, descarte, regras da prescrição, alergia com e sem justificativa, ciclo do item e vencimento).
- API: `tests/api/test_pharmacy_api.py` (lotes e rotas legadas juntos, prescrição e dispensação por HTTP, 404/409/422, linha do tempo).
- Frontend: `tests/frontend/pages.smoke.mjs` abre `/app/farmacia`.

## Fora do escopo

- Pedidos de compra a fornecedores.
- Receita digital com assinatura e integração com órgãos reguladores.
- Checagem real de interações e alergias (a correspondência é só por texto, didática).
- Conversão automática entre unidades.
- Autenticação: o papel é verificado pelo tipo do profissional (ADR-002, ADR-015).
