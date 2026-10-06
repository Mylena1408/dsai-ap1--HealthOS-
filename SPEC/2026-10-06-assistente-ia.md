# Assistente de IA educacional (2026-10-06)

## O quê e por quê

Pacientes e profissionais querem entender o prontuário de forma rápida: um resumo organizado, a explicação de um exame, observações sobre o acompanhamento e respostas a perguntas simples. O assistente faz isso sobre dados **fictícios** e nunca emite diagnóstico nem prescrição.

A aplicação depende só da interface `AIService`. A configuração `AI_PROVIDER` escolhe o provedor: o modo demonstração funciona sem chave e sem rede (respostas determinísticas), e o provedor Claude é opcional (ADR-021).

## Modelo de dados (resumo)

Tabelas novas: `assistant_conversations`, `assistant_messages` (histórico só por acréscimo).

- **Funções (`AIFeature`):** `RESUMO_PRONTUARIO`, `ANALISE_EXAME`, `ORIENTACAO_SINTOMAS`, `OBSERVACOES`, `CHAT`.
- **PatientContext:** `patient_id`, `first_name`, `age`, `facts`. Cada fato (`ContextFact`) tem `category` e `text`. Categorias usadas: `Alergia`, `Condição`, `Medicamento`, `Exame`, `Sinal vital`, `Consulta`, `Health Score`.
- **Resposta (`AIResponse`):** `feature`, `text`, `provider`, `model`, `suggestions`, `facts_used`, `urgent`, `disclaimer`.
- **Conversation:** `title` (até 120 caracteres; padrão "Nova conversa"), `patient_id` (opcional), `status`, `messages`, `created_at`, `updated_at`.
- **Estados da conversa (`ConversationStatus`):** `ATIVA`, `ARQUIVADA`.
- **ChatMessage:** `role`, `content`, `created_at`, `provider`, `suggestions`, `facts_used`, `urgent`.
- **Papéis (`MessageRole`):** `USUARIO`, `ASSISTENTE`.
- **Configuração:** `AI_PROVIDER` aceita `demo` (padrão) ou `anthropic`. `AI_MODEL` tem padrão `claude-opus-5-5`.

## Rotas (`/api/v1`)

- `GET /ai/status`
- `POST /ai/patients/{patient_id}/summary`
- `POST /ai/patients/{patient_id}/insights`
- `POST /ai/exams/{exam_id}/analysis`
- `POST /ai/symptoms` (corpo: `description`, `patient_id` opcional)
- `POST /conversations`
- `GET /conversations` (filtros `patient_id`, `status`, `limit`, `offset`)
- `GET /conversations/{conversation_id}`
- `POST /conversations/{conversation_id}/messages`
- `POST /conversations/{conversation_id}/archive`

Página da interface: `/app/assistente`.

## Critérios de aceitação

### Aviso obrigatório
- Toda resposta traz o aviso: "As informações apresentadas são educacionais e não substituem avaliação profissional. Dados fictícios; nenhum diagnóstico é emitido."
- `GET /ai/status` informa `provider`, `model`, `demo_mode` e o mesmo aviso.

### Contexto mínimo, sem identificadores
- O contexto leva só o primeiro nome, a idade e fatos clínicos.
- CPF, e-mail, telefone, endereço e convênio nunca entram no contexto.
- Fatos incluídos: alergias ativas, condições ativas, diagnósticos recentes, medicamentos em uso, até 5 exames liberados (com os itens fora da referência), resumo dos sinais vitais (sem altura), última e próximas consultas e o Health Score, quando houver nota.
- Os fatos usados voltam na resposta (`facts_used`), para transparência.
- Paciente inexistente retorna 404.

### Funções de IA
- Resumo e observações exigem paciente existente (404).
- A explicação de exame só vale para resultado liberado. Exame não liberado retorna 400. Exame inexistente retorna 404.
- Sintomas: a descrição tem de 3 a 2000 caracteres (422 fora disso). O paciente é opcional.

### Sinais de alerta (SAMU 192)
- **Em qualquer provedor**, sintomas ou mensagens do chat com sinais de alerta (ex.: "dor no peito", "falta de ar", "desmaio", "convulsão", "sangramento intenso", "pensamentos suicidas") recebem a resposta padrão de urgência, com `urgent = true`.
- O texto orienta: procurar atendimento de urgência agora ou ligar para o SAMU (192), com o aviso educacional.
- A detecção é feita pelo caso de uso **antes** de chamar o provedor e ignora acentos e maiúsculas. Havendo sinal de alerta, o provedor de IA não é chamado: nenhum dado do paciente sai do sistema.
- A resposta de urgência identifica o provedor configurado e o modelo `regra-de-seguranca`. A auditoria registra `urgent = true`.
- No chat, a pergunta e a resposta de urgência são gravadas na conversa como qualquer troca.
- Além disso, o prompt de sistema do provedor Claude também manda orientar atendimento de urgência diante desses sinais (segunda camada).

> Revisão de 2026-10-06: antes, a garantia valia só no modo demonstração; no provedor Claude a orientação dependia do modelo seguir o prompt.

### Modo demonstração (`demo`)
- Não usa rede nem modelo de linguagem. Mesmas entradas geram a mesma resposta.
- Identifica-se como `demo` / `regras-deterministicas`.
- No chat, sem paciente selecionado, pede que um paciente seja escolhido.
- Pergunta do tipo "qual diagnóstico tenho" recebe recusa e a lista do que já foi registrado pelos profissionais.

### Provedor Claude (`anthropic`)
- É opcional: depende do pacote de `requirements-ai.txt`, importado só quando usado.
- O prompt de sistema proíbe diagnóstico, prescrição e mudança de dose, e manda usar só os fatos do contexto.
- Recusa do modelo vira resposta educada ("Não posso ajudar com esse pedido...").
- SDK ausente ou erro do SDK (conexão, limite, status) vira 503.
- No chat, envia até as 20 últimas mensagens; a pergunta atual vai com o contexto atualizado.

### Conversas
- Criar conversa com paciente inexistente retorna 404. A criação retorna 201 com estado `ATIVA`.
- Enviar mensagem retorna 201 com a pergunta (`USUARIO`) e a resposta (`ASSISTENTE`).
- A mensagem não pode ser vazia e tem no máximo 2000 caracteres (422).
- A primeira mensagem vira o título quando a conversa ainda se chama "Nova conversa".
- A listagem traz as conversas sem as mensagens. O detalhe traz as mensagens.
- Conversa arquivada não aceita mensagem (409). Arquivar de novo retorna 409. Conversa inexistente retorna 404.
- Se o provedor falhar, nenhuma mensagem é gravada.

### Auditoria sem conteúdo
- Cada uso publica `ASSISTENTE_CONSULTADO` com função, provedor, modelo e se houve orientação de urgência.
- O conteúdo da pergunta e da resposta nunca vai para a auditoria.

## Testes esperados

- Unidade: `tests/unit/test_assistant.py` (regras da conversa, resumo determinístico, explicação de exame, sinais de alerta, sintomas sem alerta, intenções do chat, chat sem paciente, formato da chamada ao Claude, histórico com contexto atualizado, recusa e indisponibilidade).
- Integração: `tests/integration/test_assistant_use_case.py` (contexto sem identificadores, funções sobre dados reais, chat persistido, falha do provedor vira 503 sem gravar, sinais de alerta respondidos sem chamar o provedor — inclusive com um provedor que não seja o demo).
- API: `tests/api/test_assistant_api.py` (modo demonstração, resumo, observações e exame, 400/404/422, sintomas, ciclo da conversa com 409).
- Frontend: `tests/frontend/pages.smoke.mjs` abre `/app/assistente` com resumo e chat.

## Fora do escopo

- Diagnóstico, prescrição ou qualquer decisão clínica.
- Uso com dados reais de pacientes.
- Envio de identificadores diretos a provedores externos.
- Respostas em streaming.
- Autenticação e controle de quem pode consultar o assistente (ADR-002).
