# Responsividade e acessibilidade (2026-10-10)

## O quê e por quê

Fase 8 da modernização (`2026-10-10-modernizacao-visao-geral.md`). A revisão em navegador real
(`tests/frontend/a11y.review.mjs`, ADR-025) rodava o axe só em 1440 px, com WCAG 2.1, e abria cada
página com o perfil padrão: as telas das Fases 3 a 6 (visão Enfermagem, área de IDs dos médicos, aba
Evolução, modal de dispensa, seletor de paciente do portal) não eram auditadas, e faltavam 360 e
390 px. Esta parte amplia a revisão; as correções do que ela encontrar vêm numa etapa seguinte,
com aprovação.

## Modelo de dados (resumo)

Sem tabelas nem rotas novas. Só o script de revisão muda.

## Rotas (`/api/v1`)

Sem rotas novas. O script usa as existentes para preparar os estados: `GET /patients`,
`GET /professionals`, `POST /patients/{id}/evolutions` (um rascunho no banco descartável).

## Critérios de aceitação da revisão

- Larguras: 1440, 1024, 768, 390, 375 e 360 px, em todas as páginas.
- axe em todas as larguras, com as regras WCAG 2.0, 2.1 e 2.2 nos níveis A e AA (inclui
  `target-size`).
- Estados auditados (axe e rolagem horizontal em 1440, 768 e 360 px):
  Painel com perfil Enfermeiro (visão Enfermagem), com perfil Médico (área "Médicos disponíveis"),
  com perfil Paciente (alertas); aba Evolução com o editor aberto; modal de dispensa aberto; portal
  com o modal "Minhas consultas" e a lista do seletor de paciente aberta.
- Teclado: menu "Para você" (Enter abre, Tab entra, Esc fecha e devolve o foco); seletor de paciente
  dentro de um modal do portal (setas, Enter escolhe sem fechar o modal, Esc fecha só a lista);
  menu móvel em 360 px.
- Os testes já existentes continuam.

## Testes esperados

- `npm run a11y` com servidor local e banco descartável. O resultado alimenta o relatório da fase.

## Fora do escopo

- Corrigir o que a revisão encontrar (etapa seguinte, com aprovação).
- Leitura com leitor de tela real (ADR-025).
