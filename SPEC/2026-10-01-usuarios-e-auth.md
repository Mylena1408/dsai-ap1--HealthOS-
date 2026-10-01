# Usuários, autenticação e auditoria (2026-10-01)

## O quê e por quê

Um sistema hospitalar lida com dados sensíveis. Só pessoas autenticadas e autorizadas podem usar cada função, e toda alteração de dado precisa deixar rastro. Esta parte cobre cadastro de usuários, login com JWT, permissões por perfil (RBAC) e auditoria automática.

## Modelo de dados (resumo)

- **User:** `full_name` (mínimo 3 caracteres), `email` (único), `cpf` (único), `password_hash`, `phone`, `is_active`.
- **Role:** `name`, `description`, lista de permissões.
- **Permission:** `code` no formato `modulo:acao` (exige o caractere `:`), `description`.
- **AuditLog:** `user_id`, `timestamp`, `action` (`CREATE`, `UPDATE`, `DELETE`), `resource`, `resource_id`, `old_value`, `new_value`.

## Rotas

- `POST /api/v1/auth/login`
- `POST /api/v1/admin/users`, `GET /api/v1/admin/users`, `PATCH /api/v1/admin/users/{id}`, `DELETE /api/v1/admin/users/{id}`

## Critérios de aceitação

### Cadastro
- E-mail com formato válido e CPF com 11 dígitos, não todos iguais.
- E-mail e CPF já cadastrados são recusados com erro de conflito claro.
- A senha é guardada **apenas como hash com sal** (bcrypt ou argon2). Nunca em texto puro, nem em logs nem em respostas da API.
- A resposta de criação e de listagem nunca inclui a senha ou o hash.

### Login
- O login recebe e-mail e senha e devolve `access_token`, `refresh_token`, `user_id` e `full_name`.
- A verificação compara a senha informada com o hash.
- Credenciais inválidas e usuário inativo retornam a mesma mensagem genérica.
- O token de acesso expira em 30 minutos (`ACCESS_TOKEN_EXPIRE_MINUTES`) e o de atualização em 7 dias (`REFRESH_TOKEN_EXPIRE_DAYS`). Cada token carrega o campo `type` (`access` ou `refresh`).
- Token expirado, adulterado ou do tipo errado retorna 401 nas rotas protegidas. Um `refresh_token` não é aceito como token de acesso.

### Autorização
- Cada rota protegida declara as permissões que exige. Sem token, 401. Com token mas sem permissão, 403 com a permissão faltante na mensagem.
- Quando uma rota exige mais de uma permissão, o usuário precisa ter todas.
- As permissões de um usuário vêm dos papéis a ele atribuídos.
- Existe caso de uso para atribuir papel a um usuário. Só quem tem `user:update` pode usá-lo.

### Gestão de usuários
- Criar, listar e atualizar exigem `user:create`, `user:read` e `user:update`.
- `DELETE` faz desativação lógica (`is_active = false`), não apaga a linha.
- Usuário inativo não faz login.

### Auditoria
- Todo `INSERT`, `UPDATE` e `DELETE` nos modelos persistidos gera um `AuditLog` automaticamente, por interceptador de eventos do SQLAlchemy, sem chamada manual nos casos de uso.
- No `UPDATE`, o log guarda os campos alterados com valor antigo e novo. No `DELETE`, guarda os valores removidos.
- O `user_id` do log é o usuário autenticado da requisição.
- Dados sensíveis (hash de senha) não aparecem nos valores do log.

## Testes esperados

- Unidade: validação de `User` (e-mail, CPF, nome curto) e de `Permission` (código sem `:`), emissão e decodificação de tokens, ativar e desativar usuário.
- Integração: login válido e inválido, rota protegida com e sem permissão, criação com e-mail duplicado, geração de `AuditLog` ao criar e alterar um registro.

## Fora do escopo

- Login social e autenticação em dois fatores.
- Rota de renovação de token com o `refresh_token`.
- Recuperação de senha por e-mail.
- Bloqueio por tentativas excessivas de login.
