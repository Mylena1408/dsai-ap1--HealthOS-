# Farmácia: dispensa segura (2026-10-10)

## O quê e por quê

Fase 5 da modernização (`2026-10-10-modernizacao-visao-geral.md`). Problemas encontrados:

- O formulário de dispensa da tela `/app/farmacia` ficava ativo durante o envio e continuava enviável
  depois do sucesso. O servidor só barra quantidade acima do saldo, então um segundo clique com
  quantidade parcial registrava outra dispensação.
- O card "Prescrever Medicação" do portal abria um formulário de dispensa pela rota legada
  `POST /pharmacy/dispense/{med}/{loc}`, que baixa estoque sem receita, paciente nem lote, com IDs
  digitados à mão.
- Dispensar e descartar lote não pediam confirmação.

Decisão D5 = (a): o portal deixa de usar a dispensa legada; a rota continua na API.

## Modelo de dados (resumo)

Sem tabelas e sem rotas novas. Nenhuma mudança no back-end.

## Rotas (`/api/v1`)

Sem rotas novas nem alteradas. A tela usa as já existentes `POST /dispensations`,
`POST /stock/lots`, `POST /stock/lots/{id}/discard`. `POST /pharmacy/dispense/{med}/{loc}` continua
disponível (Swagger e testes legados), mas nenhuma tela a usa.

## Critérios de aceitação

### Dispensar (`/app/farmacia`)
- O farmacêutico vem escolhido quando o perfil é de um farmacêutico ativo.
- Antes de enviar: pelo menos um item com quantidade maior que 0 e nenhum acima do saldo; senão,
  mensagem no formulário e nada é enviado.
- Confirmação com o resumo (itens e quantidades, farmacêutico, local). Cancelar não envia nada.
- Durante o envio, o botão fica desativado. Depois do sucesso, quantidades, farmacêutico, local e
  botão ficam bloqueados, o botão passa a "Dispensado" e a fila é atualizada; para outra
  dispensação é preciso fechar e abrir de novo.
- Em caso de erro, o formulário volta a ficar editável.

### Descartar lote vencido
- Pede confirmação com o número do lote; cancelar não envia nada. Botão desativado durante o envio.

### Entrada de lote
- Botão desativado durante o envio.

### Portal
- O card "Prescrever Medicação" vira link para o prontuário (`/app/prontuario`), onde a prescrição é
  feita na aba Medicamentos, e mostra o link "Dispensar na Farmácia" (`/app/farmacia`).
- O formulário de dispensa legada sai do portal.

## Testes esperados

- `npm run flow` (`tests/frontend/pharmacy.flow.mjs`): farmacêutico do perfil escolhido; cancelar
  a confirmação não dispensa; duplo clique gera uma única dispensação (contada por
  `GET /dispensations?prescription_id=`); formulário bloqueado depois do sucesso; quantidade acima
  do saldo é barrada na tela; cancelar o descarte mantém o lote; o portal não tem mais o formulário
  legado e aponta para prontuário e farmácia.
- Regressão: `npm test`, `npm run smoke`, `npm run a11y`, `pytest`.

## Fora do escopo

- Remover ou alterar a rota legada `/pharmacy/dispense`.
- Mudar FEFO, regras de prescrição ou de estoque.
