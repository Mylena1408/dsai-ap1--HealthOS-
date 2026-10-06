# Busca global (2026-10-06)

## O quê e por quê

Com muitas páginas, achar um paciente, uma fatura ou um código de amostra exigia saber antes em qual módulo procurar. A busca global recebe um termo e devolve resultados agrupados por tipo, cada um com o link da página certa.

O CPF aparece mascarado nos resultados: basta para conferir a pessoa, sem expor o documento inteiro.

## Modelo de dados (resumo)

Sem tabelas novas. Estruturas de resposta (`search_dto.py`):

- **SearchResultDTO:** `query` (termo normalizado), `groups` (apenas grupos com resultado).
- **SearchGroupDTO:** `key`, `label`, `total` (correspondências no banco), `items` (no máximo `per_group`).
- **SearchItemDTO:** `title`, `subtitle`, `link`.
- **Grupos (`key`), nesta ordem:** `pacientes`, `profissionais`, `medicamentos`, `exames`, `faturas`, `relatorios`.
- **Limites (`search_use_case.py`):** `MIN_LENGTH = 2`, `MAX_LENGTH = 80`, `DEFAULT_PER_GROUP = 5`.

## Rotas (`/api/v1`)

- `GET /search` (parâmetros `q` e `per_group`)

Página: `/app/busca` (aceita `?q=<termo>`).

## Critérios de aceitação

### Validação
- Sem `q`, retorna 422.
- `q` com mais de 80 caracteres retorna 422.
- `per_group` fora de 1 a 20 retorna 422. O padrão é 5.
- Espaços repetidos são reduzidos a um. Termo com menos de 2 caracteres retorna 400 ("Digite ao menos 2 caracteres.").

### Onde cada grupo procura
- Pacientes: nome contém o termo. Se o termo tiver 3 dígitos ou mais, também procura esses dígitos no CPF.
- Profissionais: nome ou número de registro.
- Medicamentos: nome comercial ou nome genérico.
- Exames: código da amostra.
- Faturas: número da fatura.
- Relatórios: título e descrição do catálogo, sem diferenciar maiúsculas e acentos.
- `%` e `_` digitados são tratados como texto comum, não como curinga. Buscar `%%` não traz resultados.

### Resultados
- Grupos sem resultado não aparecem.
- `total` é o número de correspondências no banco, mesmo quando a lista mostra só parte delas.
- Paciente: subtítulo com idade e CPF mascarado no formato `***.456.789-**`. O CPF completo não aparece na resposta.
- Links:
  - paciente → `/app/prontuario?patient=<id>`;
  - profissional → `/app/consultas?professional=<id>`;
  - medicamento → `/app/farmacia`;
  - exame → `/app/prontuario?patient=<id do paciente>`;
  - fatura → `/app/financeiro?invoice=<id>`;
  - relatório → `/app/relatorios?report=<key>`.

### Página e atalho
- A página pede 8 resultados por grupo e mostra "X de Y" quando há mais, com a dica de refinar o termo.
- O termo buscado é destacado com `<mark>` por `highlightTerm` (em `static/js/core/dom.js`), que escapa o HTML antes de destacar e não casa dentro de entidades como `&amp;`.
- O termo fica na URL (`?q=`); abrir a página com `?q=` já executa a busca.
- A barra de navegação tem um campo de busca que envia para `/app/busca`; no celular, o campo fica no menu.
- A tecla `/` leva o foco ao campo de busca da barra, exceto quando o foco já está em um campo de texto.

## Testes esperados

- Unidade: `tests/unit/test_search.py` (máscara de CPF, comparação sem acento, escape de curingas, grupos e links, termo curto rejeitado, CPF só com dígitos suficientes).
- API: `tests/api/test_search_api.py` (busca por nome e por CPF, CPF mascarado, `%%` sem resultados, grupo de relatórios, validações 400 e 422).
- Frontend: `tests/frontend/components.test.mjs` (destaque sem injeção de HTML), `tests/frontend/pages.smoke.mjs` (busca de faturas e abertura do detalhe no financeiro), `tests/frontend/a11y.review.mjs` (tecla `/`).

## Fora do escopo

- Busca por texto livre dentro do prontuário (evoluções, diagnósticos).
- Busca tolerante a erros de digitação.
- Paginação dentro de um grupo.
