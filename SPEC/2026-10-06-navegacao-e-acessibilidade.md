# Navegação e acessibilidade (2026-10-06)

## O quê e por quê

Com 16 páginas, a barra de links soltos não cabia: em telas largas metade dos itens ficava escondida e, no celular, os links sumiam. Os testes em DOM simulado não mediam layout, então o problema não aparecia nos testes (ADR-025).

Esta parte agrupa a navegação em menus, cria um menu para celular, torna o seletor de paciente e os gráficos utilizáveis por teclado e leitor de tela, e acrescenta uma revisão automática em navegador real.

## Modelo de dados (resumo)

Sem tabelas novas. Estruturas do frontend:

- **`NAV_LINKS`** (`static/js/core/layout.js`): link direto `painel`.
- **`NAV_GROUPS`:**
  - `atendimento` ("Atendimento"): `prontuario`, `consultas`, `laboratorio`, `farmacia`, `assistente`.
  - `gestao` ("Gestão"): `financeiro`, `relatorios`, `alertas`, `profissionais`, `auditoria`, `status`, `docs` (Documentação da API, abre em nova aba).
- **Opções dos gráficos:**
  - `renderBarChart(container, items, options)`: `items` = `[{ label, value }]`; `options` = `{ color, unit, format, ariaLabel }`.
  - `renderLineChart(container, series, options)`: `series` = `[{ name, color, points: [{ t, v, note? }] }]`; `options` = `{ unit, format, height, reference: { min?, max? }, ariaLabel }`.
- **Favicon:** `static/favicon.svg`.

## Rotas (`/api/v1`)

Sem rotas novas na API. Fora de `/api/v1`:

- `GET /favicon.ico` (devolve `static/favicon.svg` como `image/svg+xml`; não aparece em `/docs`).

Revisão em navegador: `npm run a11y` em `tests/frontend` (executa `node a11y.review.mjs`).

## Critérios de aceitação

### Menus agrupados
- A barra mostra Painel e os menus "Atendimento" e "Gestão".
- Cada menu é um botão com `aria-expanded` e `aria-controls` (padrão *disclosure*).
- O menu abre e fecha com clique ou Enter. Abrir um menu fecha os outros.
- Esc fecha o menu aberto e devolve o foco ao botão.
- Clique fora da barra ou foco saindo do grupo fecha o menu.
- A página atual recebe `aria-current="page"` e o grupo que a contém fica destacado.
- O logo leva ao portal (`/`).

### Menu móvel
- Abaixo da largura `md`, um botão "Abrir menu" (`#nav-toggle`) abre o painel `#nav-mobile`.
- O painel traz um campo de busca e todas as páginas, separadas pelos títulos dos grupos.

### Seletor de paciente
- O campo vira `combobox` com `aria-autocomplete="list"`, `aria-controls` e `aria-expanded`; a lista tem `role="listbox"`.
- As sugestões vêm de `GET /api/v1/patients?q=` (até 8), com 250 ms de espera após a digitação.
- Seta para baixo ou para cima percorre as opções em ciclo e atualiza `aria-activedescendant` e `aria-selected`.
- Enter escolhe a opção ativa sem enviar o formulário. Esc fecha a lista.
- Respostas antigas são ignoradas quando o texto já mudou.
- Sem resultado, mostra "Nenhum paciente encontrado.".

### Gráficos
- O `<svg>` tem `role="group"` e `aria-label`.
- Barras: cada barra tem `tabindex="0"`, `role="img"` e `aria-label` "rótulo: valor"; o foco mostra a dica com o valor.
- Linha: a área do gráfico tem `tabindex="0"` e `role="img"`; no foco, a dica começa na última medição e as setas esquerda e direita percorrem as medições.
- A opção `format` define o texto do valor no rótulo, na dica e no `aria-label`. Sem ela, usa o número em pt-BR e a unidade.
- O espaço do rótulo de valor é calculado pelo tamanho do texto.
- Séries constantes ou com um só ponto não geram coordenadas inválidas (`NaN`). Com uma só série, não há legenda.

### Favicon
- Todas as páginas em `static/pages` e o `index.html` apontam para `/static/favicon.svg`.
- `/favicon.ico` responde com o mesmo SVG.

### Revisão em navegador real (`npm run a11y`)
- Usa o Edge ou Chrome instalado (puppeteer-core) ou o caminho em `BROWSER_PATH`. Sem navegador, termina com código 2.
- Abre 15 endereços (portal e páginas `/app/...`) em 1440, 1024, 768 e 375 px.
- Falha com rolagem horizontal, erro no console, texto "Erro:" na tela ou violação WCAG 2.1 AA do axe-core (medida em 1440 px).
- Testa por teclado: menu Gestão (Enter, Tab, Esc), menu móvel com pelo menos 12 links, seletor de paciente (setas e Enter), axe com o modal de fatura aberto e a tecla `/`.
- Termina com código 1 se houver qualquer falha.

## Testes esperados

- Frontend: `tests/frontend/a11y.review.mjs` (revisão em navegador real), `tests/frontend/components.test.mjs` (gráficos: tooltip por teclado, casos-limite, formatador, papéis e nomes acessíveis), `tests/frontend/pages.smoke.mjs` (páginas em DOM simulado).

## Fora do escopo

- Leitura com leitor de tela real (o ADR-025 recomenda NVDA à parte).
- Tema escuro e preferências de tamanho de fonte.
- Execução de `npm run a11y` no deploy.
