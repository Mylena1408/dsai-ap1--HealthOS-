# Roteiro de demonstração (≈ 15 minutos)

Roteiro para apresentar o HealthOS em sala. Todos os dados são **fictícios** e gerados pelo seed;
nada aqui é diagnóstico ou orientação médica real.

## Preparação (antes da apresentação)

```bash
venv\Scripts\Activate.ps1            # Linux/macOS: source venv/bin/activate
python -m scripts.seed_demo           # 50 pacientes e todo o resto; pode rodar de novo sem duplicar
uvicorn main:app --reload
```

- Abra `http://127.0.0.1:8000/` e deixe o perfil de demonstração (canto superior direito) em
  **Administração**.
- Para conferir antes que tudo está em ordem: em `tests/frontend`, rode `npm run smoke` e
  `npm run a11y` com `HEALTHOS_URL=http://127.0.0.1:8000`.
- O assistente funciona sem internet (`AI_PROVIDER=demo`). Só use `anthropic` se a chave estiver
  configurada e houver rede.

## 1. Visão geral (2 min) — Painel

1. **Painel** → visão *Administração*: totais, consultas por dia, exames por situação e a
   distribuição do Health Score.
2. Troque o perfil para um **paciente** (no topo): o painel muda para o Health Score explicado por
   componente. Reforce que é um *indicador de acompanhamento*, não de saúde.
3. Mostre a navegação: Painel, **Atendimento** e **Gestão**; a tecla `/` leva à busca.

## 2. Jornada clínica (5 min) — Atendimento

1. **Gestão → Alertas**: filtre a categoria *Laboratorial* e abra um alerta "Exame fora da
   referência". Ele aponta o paciente.
2. **Atendimento → Prontuário** desse paciente:
   - *Linha do tempo*: consultas, exames, prescrições e sinais vitais em ordem;
   - *Exames*: valores com classificação (ícone + texto), clique no analito para o gráfico de
     evolução e use **Explicar resultado (IA)** — a explicação é educacional e traz o aviso.
3. **Assistente** (botão no cabeçalho do prontuário): **Resumir prontuário**; depois pergunte no
   chat "Quais medicamentos estão em uso?". Para mostrar a segurança, escreva "estou com dor no
   peito" — a resposta orienta procurar urgência (SAMU 192) e não diagnostica.
4. **Laboratório**: o fluxo do exame (solicitado → coletado → … → liberado); cada exame mostra só as
   ações permitidas na situação atual (a API recusa as demais com 409).
5. **Farmácia**: fila de prescrições ativas, dispensação por lote (vence primeiro, sai primeiro).

## 3. Gestão (5 min)

1. **Gestão → Financeiro**: indicadores do mês, gráfico faturado × recebido (botão *Ver tabela*).
   - Filtre *Situação: Em atraso* e abra uma fatura: total, parte do convênio e do paciente.
     Registre um pagamento parcial e depois o restante — a situação muda para *Paga*.
   - Em **Faturar atendimentos**, escolha um paciente (há vários com consultas/exames sem fatura),
     marque os atendimentos e gere a fatura. Tente faturar de novo: os mesmos atendimentos não
     aparecem mais.
2. **Gestão → Relatórios**: *Faturas emitidas* → *Visualizar*, depois **Baixar PDF** e **Baixar
   CSV** (abre no Excel em português).
3. **Gestão → Auditoria**: as ações que você acabou de fazer (pagamento, fatura, relatório
   exportado) estão registradas — o que aconteceu, nunca o conteúdo sensível.
4. **Busca** (`/`): digite `FAT-` e abra uma fatura; digite parte de um nome de paciente e note o
   CPF mascarado.

## 4. Bastidores (3 min) — para a banca técnica

- `/docs`: a API documentada (Swagger).
- `docs/DECISOES.md`: as decisões de arquitetura (ADR-001 a ADR-025), por exemplo "em atraso"
  derivado do vencimento e a IA desacoplada com modo demonstração.
- Testes: `pytest` (backend), `npm test`, `npm run smoke` e `npm run a11y` (frontend, inclusive
  acessibilidade em navegador real).
- `/status` e `/metrics`: versão, banco e métricas das requisições.

## Se algo der errado

| Sintoma | O que fazer |
|---|---|
| Páginas vazias | Rode `python -m scripts.seed_demo` e recarregue |
| "Não foi possível conectar à API" | Confira se o `uvicorn` está rodando na porta usada |
| Assistente responde 503 | Provedor real sem rede/chave: volte `AI_PROVIDER=demo` no `.env` e reinicie |
| Datas "antigas" nos dados | O seed usa a data do dia em que rodou; rode de novo em um banco novo |
