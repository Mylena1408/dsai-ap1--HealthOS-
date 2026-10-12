# Contagem de linhas do HealthOS

Medição feita em 2026-10-11 com o [cloc](https://github.com/AlDanial/cloc) v2.06,
sobre os arquivos versionados no git (commit `812d9e3`, branch `feature/modernizacao-interface`).

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
| Markdown   | 43       | 2.519     | 1.858       | 4.377        | 8.215    | 12.592 |
| JSON       | 3        | 0         | 0           | 0            | 1.861    | 1.861  |
| Text       | 3        | 2         | 0           | 2            | 43       | 45     |
| YAML       | 1        | 0         | 13          | 13           | 21       | 34     |
| Dockerfile | 1        | 4         | 5           | 9            | 15       | 24     |
| INI        | 1        | 0         | 0           | 0            | 6        | 6      |
| SVG        | 1        | 0         | 0           | 0            | 1        | 1      |
| **Total**  | **53**   | **2.525** | **1.876**   | **4.401**    | **10.162** | **14.563** |

O JSON é quase todo o `tests/frontend/package-lock.json`.

## Projeto inteiro

| Arquivos | Em branco | Comentários | Não efetivas | **Efetivas** | **Total** |
|---------:|----------:|------------:|-------------:|-------------:|----------:|
| 346      | 6.960     | 3.369       | 10.329       | **33.089**   | **43.418** |

## Arquivos desta pasta

- `cloc-resumo.txt`: saída original do cloc, por linguagem.
- `cloc-por-arquivo.txt`: saída do cloc arquivo por arquivo (`--by-file`).
