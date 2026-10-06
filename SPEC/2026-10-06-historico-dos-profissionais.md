# Histórico dos profissionais (2026-10-06)

## O quê e por quê

O detalhe de um profissional mostrava cadastro e agenda, mas não o que ele já fez no sistema. Esta parte reúne, em um histórico único e do mais recente para o mais antigo, as consultas, sinais vitais, prescrições, dispensações e exames ligados a cada profissional.

Para o histórico da enfermagem ter conteúdo, o seed passa a registrar os sinais vitais em nome dos enfermeiros. Os dados de exemplo ficam documentados em `docs/DADOS_DE_EXEMPLO.md`, e uma falha no seed não impede mais o sistema de subir.

## Modelo de dados (resumo)

Sem tabelas novas. Usa colunas que já existiam em cada registro:

- **Tipos de atividade (`ActivityKind`), com o valor da API:** `CONSULTA`, `SINAIS_VITAIS`, `PRESCRICAO`, `DISPENSACAO`, `EXAME_SOLICITADO`, `EXAME_VALIDADO`.
- **Origem de cada tipo (profissional / data):**
  - `CONSULTA`: `appointments.professional_id` / `start_time`.
  - `SINAIS_VITAIS`: `vital_signs.professional_id` / `recorded_at`.
  - `PRESCRICAO`: `prescriber_id` / `issued_at`.
  - `DISPENSACAO`: `pharmacist_id` / `dispensed_at`.
  - `EXAME_SOLICITADO`: `requested_by` / `requested_at`.
  - `EXAME_VALIDADO`: `validated_by` / `validated_at`.
- **ActivityItem / ActivityItemDTO:** `kind`, `occurred_at`, `description`, `patient_id`, `patient_name`.
- **ProfessionalActivityDTO:** `professional_id`, `totals` (quantidade por tipo, só os tipos com registro), `items` (mais recentes primeiro).

## Rotas (`/api/v1`)

- `GET /professionals/{professional_id}/activity` (parâmetro `limit`, padrão 20, de 1 a 100)

Página: `/app/profissionais` (seção "Histórico de atividades" no detalhe do profissional).

## Critérios de aceitação

### Consulta do histórico
- Profissional inexistente retorna 404.
- `professional_id` que não é UUID ou `limit` fora de 1 a 100 retorna 422.
- Só entram registros com data até o momento da consulta. Consultas futuras ficam na agenda, não no histórico.
- `totals` conta todos os registros de cada tipo até agora e omite os tipos com zero.
- `items` junta os tipos, ordena do mais recente para o mais antigo e devolve no máximo `limit` itens.
- Todo item traz o paciente (`patient_id` e `patient_name`).

### Descrição de cada item
- Consulta: "Consulta (tipo) — situação", com os rótulos legíveis em minúsculas.
- Sinais vitais: "Sinais vitais registrados", seguido dos valores presentes (PA em mmHg, FC em bpm, SpO2 em %, temperatura em °C).
- Prescrição: "Prescrição emitida — situação".
- Dispensação: "Medicamentos dispensados (local)".
- Exames: "Exame solicitado: nome do exame" e "Exame validado: nome do exame".

### Página
- Ao abrir o detalhe de um profissional, a página pede `?limit=15`.
- Mostra um selo por tipo com o total e a lista com descrição, data e hora e link do paciente para `/app/prontuario?patient=<id>`.
- Sem nenhum registro, mostra "Nenhuma atividade registrada por este profissional.".
- Em erro, mostra "Erro:" seguido da mensagem.

### Seed (`seed_vital_signs`)
- Se já houver sinais vitais no banco, o seed não cria novos.
- As medições são atribuídas aos enfermeiros em revezamento (ordenados pelo id). Sem enfermeiros, ficam sem profissional.
- O revezamento não consome números aleatórios: os demais dados do seed não mudam.
- Com o seed, cada tipo de profissional tem histórico: enfermeiro com `SINAIS_VITAIS`, médico com `CONSULTA`, farmacêutico com `DISPENSACAO`.

### Inicialização (`main.py`)
- Com `SEED_DEMO_DATA` verdadeiro, um erro no seed é registrado no log `healthos.seed` ("Falha ao gerar os dados de demonstração; o sistema segue sem eles.") e a inicialização continua.

### Documentação (`docs/DADOS_DE_EXEMPLO.md`)
- Avisa que todos os dados são fictícios.
- Explica como carregar o seed (Render, `.env` ou `python -m scripts.seed_demo`) e que ele só acrescenta dados, sem duplicar.
- Lista os profissionais por tipo, com especialidade, departamento e registro fictício, os medicamentos e os nomes dos pacientes.
- Avisa que quantidades, datas, estoques e quais pacientes têm alergias ou condições dependem do dia em que o seed rodou e devem ser consultados na tela.
- Mostra o caminho na tela para ver o histórico de cada tipo de profissional, do paciente e dos medicamentos.

## Testes esperados

- Integração: `tests/integration/test_professional_activity.py` (histórico por tipo de profissional sobre o seed, ordem do mais recente, só registros passados, limite de itens, paciente em cada item, profissional inexistente).
- Integração do seed: `tests/integration/test_demo_seed.py` (idempotência do seed).

## Fora do escopo

- Filtro do histórico por tipo ou por período.
- Paginação além de `limit`.
- Teste automatizado da proteção de falha do seed na inicialização.
