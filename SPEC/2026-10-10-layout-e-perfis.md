# Layout compartilhado e perfis (2026-10-10)

## O quê e por quê

Fase 2 da modernização (`2026-10-10-modernizacao-visao-geral.md`). O menu passa a sugerir as
telas típicas do perfil de demonstração escolhido, e o perfil de profissional passa a guardar o
tipo (médico, enfermeiro...). Nada é bloqueado: todas as telas continuam acessíveis (ADR-002,
ADR-027).

## Modelo de dados (resumo)

Sem tabelas e sem rotas novas. Estruturas do frontend:

- **Perfil** (`localStorage`, chave `healthos.profile`):
  `{ audience: 'SETOR' | 'PROFISSIONAL' | 'PACIENTE', sector?, recipient_id?, label, professional_type? }`.
  `professional_type` só existe para `PROFISSIONAL`; perfis salvos antes desta versão continuam
  válidos e recebem a sugestão genérica de profissional.
- **`static/js/core/role-nav.js`:** `PROFILE_PAGES` (ids de página por perfil) e
  `pagesForProfile(profile)`.
- **Catálogo de páginas** (`static/js/core/layout.js`): as entradas de `NAV_GROUPS` mais
  `notificacoes` e `busca`, usadas só pelo menu "Para você".

## Rotas (`/api/v1`)

Sem rotas novas. Usadas pelo seletor de perfil (já existentes): `GET /professionals?status=ATIVO`,
`GET /patients?q=`.

## Critérios de aceitação

### Menu "Para você"
- Aparece antes de "Atendimento" e "Gestão", no mesmo padrão *disclosure* (ADR-025).
- Lista as telas de `pagesForProfile` para o perfil atual, na ordem da tabela da visão geral.
- Traz o aviso: "Sugestões do perfil de demonstração. Todas as telas continuam em Atendimento e
  Gestão."
- Ao trocar de perfil, o conteúdo é refeito sem recarregar a página.
- Os links de "Para você" não recebem `aria-current`; a página atual continua marcada só nos menus
  com todas as telas.

### Todas as telas
- "Atendimento" e "Gestão" mantêm todos os itens para qualquer perfil, inclusive paciente.
- Nenhuma URL deixa de abrir.

### Menu móvel
- A barra completa aparece a partir de `lg` (1024 px); abaixo disso, o botão "Abrir menu" mostra o
  painel. Motivo: com o menu novo, a barra não cabe em 768 px.
- O painel mostra "Para você" primeiro e depois os grupos com todas as telas.

### Seletor de perfil
- Os profissionais aparecem agrupados por tipo (`<optgroup>`).
- Escolher um profissional salva `professional_type`.
- O botão do perfil informa o tipo no nome acessível, por exemplo
  "Perfil de demonstração: Ana Lima, Enfermeiro(a) (trocar)".
- O texto do seletor diz que não há senha e que o perfil muda as sugestões do menu e a caixa de
  notificações.

### Foco visível
- Links, botões e elementos com `tabindex` mostram contorno azul em `:focus-visible`.

## Testes esperados

- `tests/frontend/navigation.test.mjs` (novo, `npm test`): `pagesForProfile` para todos os perfis;
  "Para você" renderizado conforme o perfil; grupos com todas as telas para qualquer perfil;
  atualização ao trocar de perfil; ausência de `aria-current` em "Para você"; rótulo do perfil
  escapado.
- Regressão: `npm test` (componentes), `npm run smoke` e `npm run a11y`, cada conjunto com
  autorização própria.

## Fora do escopo

- Setor "Enfermagem" na caixa de notificações: `Sector` (back-end) aceita só cinco setores e
  nenhuma regra envia avisos para enfermagem. Exige alterar a API; fica para decisão futura.
- Visões novas no Painel (Fases 3, 4 e 6).
- Alterar os 14 HTML de `static/pages` e o `index.html`.
