# Contagem de linhas do HealthOS

Medição feita em 2026-10-19 com o [cloc](https://github.com/AlDanial/cloc) v2.06,
sobre os arquivos versionados no git (commit `4d85e4c`, branch `feature/modernizacao-interface`).

Comando usado:

```bash
npx cloc --vcs=git
```

## Definições

- **Efetivas**: linhas com código (coluna `code` do cloc).
- **Não efetivas**: linhas em branco + linhas só de comentário.
- **Total**: efetivas + não efetivas (todas as linhas dos arquivos).

## Código-fonte (Python, JavaScript, HTML, CSS)

| Linguagem  | Arquivos | Em branco | Comentários | Não efetivas | **Efetivas** | Total  |
|------------|---------:|----------:|------------:|-------------:|-------------:|-------:|
| Python     | 235      | 3.794     | 1.192       | 4.986        | **16.290**   | 21.276 |
| JavaScript | 42       | 538       | 274         | 812          | **5.512**    | 6.324  |
| HTML       | 15       | 96        | 19          | 115          | **1.061**    | 1.176  |
| CSS        | 1        | 7         | 8           | 15           | **64**       | 79     |
| **Total**  | **293**  | **4.435** | **1.493**   | **5.928**    | **22.927**   | **28.855** |

Do Python, 17.327 linhas (total) são da aplicação e 3.949 dos testes.
O JavaScript inclui os 9 arquivos `.mjs` de testes do frontend.

## Outros arquivos (documentação, dados e configuração)

| Tipo       | Arquivos | Em branco | Comentários | Não efetivas | Efetivas | Total  |
|------------|---------:|----------:|------------:|-------------:|---------:|-------:|
| Markdown   | 44       | 2.534     | 1.858       | 4.392        | 8.255    | 12.647 |
| JSON       | 3        | 0         | 0           | 0            | 1.861    | 1.861  |
| Text       | 5        | 2         | 0           | 2            | 414      | 416    |
| YAML       | 1        | 0         | 13          | 13           | 21       | 34     |
| Dockerfile | 1        | 4         | 5           | 9            | 15       | 24     |
| INI        | 1        | 0         | 0           | 0            | 6        | 6      |
| SVG        | 1        | 0         | 0           | 0            | 1        | 1      |
| **Total**  | **56**   | **2.540** | **1.876**   | **4.416**    | **10.573** | **14.989** |

O JSON é quase todo o `tests/frontend/package-lock.json`.

## Projeto inteiro

| Arquivos | Em branco | Comentários | Não efetivas | **Efetivas** | **Total** |
|---------:|----------:|------------:|-------------:|-------------:|----------:|
| 349      | 6.975     | 3.369       | 10.344       | **33.500**   | **43.844** |

## Comparação com a medição anterior

A medição anterior, de 2026-10-11 (commit `812d9e3`), tinha 346 arquivos, 33.089 linhas efetivas e
43.418 no total. O código-fonte não mudou (22.927 efetivas nas duas). A diferença, de 3 arquivos e
426 linhas (411 efetivas), vem só desta pasta `cloc/`, versionada depois daquela medição: este
`README.md` (Markdown) e os dois `.txt` (Text).

Os números acima valem para o commit `4d85e4c`, antes desta atualização da pasta `cloc/`.

## Arquivos desta pasta

- `cloc-resumo.txt`: saída original do cloc, por linguagem.
- `cloc-por-arquivo.txt`: saída do cloc arquivo por arquivo (`--by-file`).
