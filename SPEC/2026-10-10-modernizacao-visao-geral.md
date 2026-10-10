# Modernização da interface — visão geral (2026-10-10)

## O quê e por quê

O HealthOS já tem as telas e as APIs dos módulos, mas a interface trata todos os perfis da mesma
forma: o menu é igual para todos e o perfil de demonstração só escolhe a caixa de notificações.
A modernização organiza a interface por perfil profissional (médico, enfermagem, farmácia,
administração e demais), conecta as telas aos recursos que já existem e corrige as lacunas
encontradas no diagnóstico, sem reconstruir nada.

O trabalho segue fases com aprovação humana: relatório prévio, autorização da implementação,
autorização separada para cada conjunto de testes e relatório final. A publicação no Render tem
autorização própria. Branch: `feature/modernizacao-interface`.

## Decisões aprovadas (2026-10-10)

- **ADR-002 mantido:** sem senha, chave, token ou login. O perfil de demonstração faz o papel de
  "usuário identificado" e pode ser trocado a qualquer momento (ver adendo em `docs/DECISOES.md`).
- **D1 — Navegação:** mantém a barra superior com menus agrupados (ADR-025) e acrescenta o menu
  "Para você", com as telas típicas do perfil. Os menus "Atendimento" e "Gestão" continuam com
  todas as telas para qualquer perfil.
- **D2 — Evolução clínica:** quando a Fase 3 for autorizada, em tabela e rotas novas ligadas a
  `professionals` (as notas legadas apontam para `users`, que o sistema não cria). A rota legada
  `/clinical/notes` permanece intacta (ADR-003).
- **D3 — Enfermagem:** primeiro só com recursos existentes (sinais vitais, procedimentos,
  alergias, alertas, consulta às prescrições). A triagem fica para depois: o domínio aponta para
  `users` e `update_patient_priority` não está implementado.
- **D4 — Registro:** esta spec, uma spec por fase autorizada e o adendo ao ADR-002 com o ADR-027.

## Recomendações para manter o ADR-002

- **R1.** O perfil guarda id, nome e, para profissionais, o tipo (`professional_type`).
- **R2.** O menu orienta, não bloqueia: nenhuma URL deixa de abrir e todas as telas continuam
  nos menus "Atendimento" e "Gestão".
- **R3.** O autor de um registro é sugerido pelo perfil e pode ser trocado (Fase 3).
- **R4.** `/api/v1/auth/login`, `PermissionChecker` e `/api/v1/admin/users` ficam como estão e sem
  tela.
- **R5.** A interface informa que as sugestões vêm do perfil de demonstração e não são controle de
  acesso.
- **R6.** O `localStorage` guarda só o perfil (id, nome, tipo), nunca dados clínicos.

## Telas sugeridas por perfil

| Perfil | Telas em "Para você" |
|---|---|
| Médico | Painel, Prontuário, Consultas, Laboratório, Alertas, Assistente |
| Enfermeiro e setor Enfermagem (Fase 3) | Painel, Prontuário, Consultas, Alertas, Laboratório |
| Psicólogo, nutricionista, fisioterapeuta, outro ou tipo desconhecido | Painel, Prontuário, Consultas, Alertas |
| Farmacêutico e setor Farmácia | Painel, Farmácia, Prontuário, Alertas |
| Setor Laboratório | Laboratório, Painel, Alertas |
| Setor Recepção | Consultas, Busca, Profissionais |
| Setor Coordenação clínica | Painel, Alertas, Profissionais, Relatórios, Auditoria |
| Setor Administração | Painel, Financeiro, Relatórios, Profissionais, Auditoria, Status |
| Paciente | Painel, Notificações, Assistente |

## Fases

| Fase | Escopo | Spec |
|---|---|---|
| 0 | Diagnóstico | — (relatório na conversa) |
| 1 | Planejamento técnico | esta spec |
| 2 | Layout compartilhado e perfis | `2026-10-10-layout-e-perfis.md` |
| 3 | Médico: painel, autoria, aviso de prescrição, aba Evolução (D2) | a criar quando autorizada |
| 4 | Enfermagem com recursos existentes (D3) | a criar quando autorizada |
| 5 | Farmácia: confirmação, envio único, portal → `/app/farmacia` | a criar quando autorizada |
| 6 | Administrativo e portal sem IDs digitados | a criar quando autorizada |
| 7 | Mapa das integrações entre módulos | relatório |
| 8 | Responsividade (360, 390, 768, 1024, 1440 px) e acessibilidade | relatório |
| 9 | Regressão | relatório |
| 10 | Preparação da publicação | relatório |

## Fora do escopo

- Qualquer autenticação ou bloqueio de acesso (ADR-002).
- Remover rotas legadas ou alterar contratos existentes sem nova autorização.
- Tarefas de enfermagem, registro de cuidados e checagem de medicamentos (não há modelos nem regras).
- Etapa de build para o CSS (Tailwind continua via CDN, ADR-004).
