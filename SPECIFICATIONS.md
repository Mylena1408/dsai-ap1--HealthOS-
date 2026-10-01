# Especificações Técnicas do Projeto HealthOS

Este documento detalha as especificações técnicas de cada fase do desenvolvimento do HealthOS. O projeto foi guiado por um fluxo de engenharia: `Análise -> Planejamento -> Especificação -> Implementação -> Verificação`.

---

## 📋 Fase 1: Infraestrutura, Segurança e Gestão de Usuários
**Objetivo**: Estabelecer a base tecnológica e o controle de acesso rigoroso.

### Especificações:
- **Autenticação**: Implementação de JWT (JSON Web Tokens) para autenticação stateless.
- **Autorização (RBAC)**: Sistema de permissões granulares baseadas em strings `modulo:acao` (ex: `patient:write`).
- **Auditoria**: Interceptor de banco de dados para capturar automaticamente todas as operações de INSERT, UPDATE e DELETE, garantindo a rastreabilidade total.
- **Persistência**: Uso de SQLAlchemy 2.0 com `AsyncSession` para alta performance em I/O.

---

## 🏥 Fase 2: Núcleo de Pacientes e Prontuário Eletrônico
**Objetivo**: Gestão de dados demográficos e histórico clínico com garantia de integridade.

### Especificações:
- **Entidade Paciente**: Validação de CPF e campos demográficos obrigatórios.
- **Prontuário Imutável**: 
    - Implementação de Máquina de Estados para Notas Clínicas (`DRAFT` $\rightarrow$ `FINALIZED`).
    - Bloqueio total de edição após a finalização da nota, simulando exigências legais de registros médicos.
- **Evolução Clínica**: Estrutura de histórico temporal para acompanhamento da evolução do paciente.

---

## 📅 Fase 3: Agendamento e Triagem (Protocolo de Manchester)
**Objetivo**: Otimizar o fluxo de entrada de pacientes e evitar conflitos de agenda.

### Especificações:
- **Lógica de Agendamento**:
    - Algoritmo de detecção de sobreposição temporal: `(StartA < EndB) AND (EndA > StartB)`.
    - Gestão de slots de disponibilidade por profissional.
- **Triagem de Risco**:
    - Implementação do Protocolo de Manchester (RED, ORANGE, YELLOW, GREEN, BLUE).
    - Validações fisiológicas para sinais vitais (ex: saturação de $O_2$ entre 0-100%).
    - Fila de espera prioritária baseada no nível de urgência.

---

## 💊 Fase 4: Farmácia e Suprimentos
**Objetivo**: Gestão de estoque crítico e controle de dispensação.

### Especificações:
- **Catálogo de Medicamentos**: Padronização de unidades de medida (ML, Comprimido, Ampola) e flag de substâncias controladas.
- **Controle de Inventário**:
    - Implementação de Limiares Mínimos e Máximos (`min_threshold` / `max_threshold`).
    - Cálculo automático de status: `IN_STOCK`, `LOW_STOCK` e `OUT_OF_STOCK`.
- **Segurança de Dispensação**: Validação rigorosa de quantidade disponível antes de permitir a saída de material.

---

## 💰 Fase 5: Faturamento e Convênios
**Objetivo**: Gestão financeira de atendimentos com suporte a planos de saúde.

### Especificações:
- **Ciclo de Vida da Fatura**: Estados `DRAFT` $\rightarrow$ `PENDING` $\rightarrow$ `PAID`.
- **Modelo de Cobrança**: Itens detalhados por tipo (Consultas, Exames, Diárias) com suporte a descontos.
- **Lógica de Coparticipação**: Cálculo automático da parte do paciente baseado na porcentagem de cobertura do convênio.
- **Precisão Financeira**: Uso obrigatório de `Decimal` para evitar erros de arredondamento de ponto flutuante.

---

## 🔔 Fase 6: Notificações e BI
**Objetivo**: Comunicação em tempo real entre sistema, equipe médica e paciente.

### Especificações:
- **Arquitetura de Mensageria**: Suporte a múltiplos canais (In-App, SMS, Push, Email).
- **Priorização de Alertas**: Diferenciação entre notificações informativas e alertas críticos (ex: paciente RED na triagem).
- **Metadados de Contexto**: Inclusão de IDs de recursos nas notificações para permitir a navegação profunda (`Deep Linking`) no sistema.
- **Rastreabilidade**: Registro de data de envio e data de leitura.

---

## 🛠️ Critérios de Aceitação Gerais
Para cada fase, os seguintes critérios foram aplicados:
1. **Cobertura de Domínio**: A lógica de negócio deve residir inteiramente nas Entidades de Domínio.
2. **Isolamento**: Mudanças na Infraestrutura (ex: trocar banco de dados) não devem afetar os Casos de Uso.
3. **Validação**: Nenhuma entidade pode ser instanciada em estado inválido (`__post_init__`).
4. **Auditabilidade**: Toda alteração de dado deve gerar um log automático.
