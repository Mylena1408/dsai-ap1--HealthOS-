# Relatórios (2026-10-06)

## O quê e por quê

A gestão precisa tirar dos módulos listas prontas para conferir, imprimir ou abrir no Excel: consultas, exames, dispensações, estoque, faturas e auditoria. Esta parte reúne esses relatórios em um catálogo único, com filtros de período e situação, e entrega o mesmo resultado em JSON (tela), CSV e PDF.

O catálogo diz "o quê" cada relatório mostra (`report_catalog.py`); as consultas SQL ficam na infraestrutura (`sql_report_source.py`) e a formatação dos arquivos em `renderers.py`. Toda exportação fica registrada na trilha de auditoria.

## Modelo de dados (resumo)

Sem tabelas novas. Estruturas em memória:

- **ReportDefinition:** `key`, `title`, `description`, `columns`, `uses_period` (padrão `True`; `False` = retrato do momento), `status_options`.
- **ReportColumn:** `key`, `label`, `kind`, `width` (peso relativo da coluna no PDF).
- **Tipos de coluna (`ColumnKind`):** `texto`, `data`, `data_hora`, `moeda`, `numero`, `codigo`.
- **Relatórios do catálogo (`key`):**
  - `consultas`: situações de `AppointmentStatus` (`AGENDADA`, `CONFIRMADA`, `EM_ANDAMENTO`, `FINALIZADA`, `CANCELADA`, `NAO_COMPARECEU`).
  - `exames`: situações de `ExamStatus` (`SOLICITADO`, `AGENDADO`, `COLETADO`, `EM_PROCESSAMENTO`, `RESULTADO_REGISTRADO`, `VALIDADO`, `LIBERADO`, `CANCELADO`).
  - `dispensacoes`: sem filtro de situação.
  - `estoque`: `uses_period=False`; situação de cada lote `OK`, `VENCENDO` ou `VENCIDO`.
  - `faturas`: situações de `BillingStatus` (`RASCUNHO`, `PENDENTE`, `PAGO`, `PARCIALMENTE_PAGO`, `ATRASADO`, `CANCELADO`).
  - `auditoria`: sem filtro de situação.
- **ReportDTO (JSON):** `key`, `title`, `generated_at`, `start`, `end` (inclusivo), `status`, `columns`, `rows`, `total_rows`, `truncated`, `code_labels`, `disclaimer`.
- **Limites (`report_use_case.py`):** `MAX_ROWS = 5000`, `MAX_PERIOD_DAYS = 366`, `DEFAULT_PERIOD_DAYS = 30`.
- **Evento de auditoria:** `RELATORIO_EXPORTADO` (`EventType.REPORT_EXPORTED`).

## Rotas (`/api/v1`)

- `GET /reports` (catálogo com colunas, `uses_period`, `status_options` e `status_labels`)
- `GET /reports/{report_key}` (parâmetros `start`, `end`, `status`, `format` = `json` | `csv` | `pdf`)

Página: `/app/relatorios` (aceita `?report=<key>` para abrir um relatório já selecionado).

## Critérios de aceitação

### Catálogo
- O catálogo lista exatamente `consultas`, `exames`, `dispensacoes`, `estoque`, `faturas` e `auditoria`.
- Cada situação vem com rótulo legível em `status_labels` (ex.: `ATRASADO` → "Em atraso").
- Todo relatório do catálogo tem uma consulta correspondente na fonte de dados.

### Parâmetros e erros
- Relatório inexistente retorna 404.
- `format` fora de `json`, `csv` e `pdf` retorna 422. Data inválida retorna 422. `status` com mais de 40 caracteres retorna 422.
- Situação que não pertence ao relatório retorna 400 ("Situação inválida para este relatório").
- Data final anterior à inicial retorna 400.
- Período maior que 366 dias retorna 400.

### Período e limites
- Sem datas, o fim é hoje e o início é 29 dias antes (30 dias no total).
- O fim é inclusivo: a consulta usa até 00:00 do dia seguinte.
- O relatório `estoque` ignora o período (`start` e `end` vêm nulos) e mostra os lotes com saldo maior que 0.
- No `estoque`, lote vencido é `VENCIDO`; com validade em até 30 dias é `VENCENDO`; demais são `OK`.
- No máximo 5000 linhas. Se houver mais, `truncated` é `true`.
- As linhas de relatórios por período vêm em ordem cronológica.
- Em `faturas`, `balance` é `gross_total - amount_paid`, e o filtro `ATRASADO` traz só faturas vencidas.

### Formatos
- JSON traz `code_labels` com o rótulo de cada código presente nas colunas do tipo `codigo`.
- JSON traz o aviso `disclaimer` de dados fictícios.
- CSV usa `;` como separador, vírgula decimal, datas `dd/mm/aaaa` e BOM UTF-8 (abre no Excel em português).
- CSV e PDF mostram códigos pelo rótulo legível (ex.: `NAO_COMPARECEU` → "Não compareceu").
- CSV e PDF são enviados como anexo, com nome `healthos_<key>_<aaaammdd>-<aaaammdd>.<ext>` (ou só a data de geração no `estoque`).
- PDF em A4, em paisagem quando a soma dos pesos das colunas passa de 8, com cabeçalho (período, situação, data de geração, número de linhas) e rodapé com o aviso e a numeração de páginas.
- PDF sem linhas mostra "Nenhum registro no período.".

### Segurança
- No CSV, célula de texto que começa com `=`, `+`, `-`, `@`, tabulação ou retorno de carro recebe `'` na frente, para a planilha não executar fórmula.
- Colunas de moeda e número não recebem o prefixo.

### Auditoria
- Cada geração (JSON, CSV ou PDF) publica `RELATORIO_EXPORTADO` com relatório, formato, número de linhas, situação e período.
- O evento registra a exportação, não o conteúdo do relatório.

### Página
- A página lista o catálogo, esconde os campos de período no `estoque` e a situação quando não há opções.
- A pré-visualização mostra até 200 linhas; os links de CSV e PDF baixam o relatório inteiro.
- Com limite atingido, a página avisa para reduzir o período.

## Testes esperados

- Unidade: `tests/unit/test_reports.py` (período padrão e validações, limite de linhas e evento de auditoria, formatação brasileira, CSV com bloqueio de fórmulas, PDF com texto Unicode).
- Integração: `tests/integration/test_reports_source.py` (todos os relatórios sobre o seed, filtro de situação, saldo de faturas, situação do estoque).
- API: `tests/api/test_reports_api.py` (catálogo, formatos via HTTP, auditoria da exportação, erros 404, 422 e 400).
- Frontend: `tests/frontend/pages.smoke.mjs` (pré-visualização de faturas e download do PDF).

## Fora do escopo

- Exportação em XLSX.
- Relatórios agendados ou enviados por e-mail.
- Relatórios criados pelo usuário.
- Controle de acesso por perfil (o projeto não tem autenticação real).
