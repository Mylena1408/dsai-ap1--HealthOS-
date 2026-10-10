# Revisão de código da modernização (2026-10-10)

## O quê e por quê

Fase 9 da modernização (`2026-10-10-modernizacao-visao-geral.md`). A revisão do diff completo da
branch `feature/modernizacao-interface` em relação à `main` encontrou 10 achados; decisão D10 = (a):
corrigir todos. Nenhum contrato da API muda.

## Modelo de dados (resumo)

Sem tabelas novas. Mudam só regras de gravação e consultas internas.

## Rotas (`/api/v1`)

Sem rotas novas. Comportamento novo em `PATCH /patients/{id}/evolutions/{eid}`,
`POST /patients/{id}/evolutions/{eid}/sign` e nos equivalentes legados de `/clinical/notes`.

## Critérios de aceitação

- **R1 (integridade):** editar e assinar só gravam se a evolução ainda estiver em rascunho no banco
  (gravação condicional). Se outra operação a assinou antes, a resposta é 409 e a assinatura
  continua valendo; em `/clinical/notes` o legado continua respondendo 400.
- **R2:** no portal, trocar para um perfil que não é de paciente limpa o paciente escolhido.
- **R3:** se o resumo financeiro falhar, a visão Administração mostra o restante e "—" nos
  indicadores financeiros.
- **R4:** o evento `EVOLUCAO_ASSINADA` aparece como "Evolução assinada".
- **R5 a R7 (desempenho):** `/clinical/notes` com ID de profissional busca o profissional uma vez;
  a lista de evoluções busca nomes e tipos dos profissionais numa só consulta; o histórico legado lê
  o paciente uma vez.
- **R8:** o seletor de perfil e o seletor de autor usam a mesma lista de profissionais (cache) e o
  mesmo agrupamento por tipo.
- **R9:** `whileBusy` passa para `core/dom.js`.
- **R10:** a dispensa usa uma só condição de envio único (formulário bloqueado ou botão desativado).

## Testes esperados

- Integração: assinatura seguida de gravação de uma cópia antiga em rascunho → 409, assinatura
  mantida. Unidade: rótulo do evento.
- `npm run flow`: troca de perfil limpa o paciente no portal; duplo clique na dispensa continua
  gerando uma só dispensação.
- Regressão final: `pytest`, `npm test`, `npm run smoke`, `npm run flow`, `npm run a11y`, roteiro I1.

## Fora do escopo

- Bloqueio pessimista ou fila de gravação; controle de acesso (ADR-002).
