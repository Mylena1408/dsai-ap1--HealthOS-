# Dados de exemplo do HealthOS

> **Todos os dados abaixo são fictícios**, gerados automaticamente pelo seed de demonstração. Nenhum
> nome, CPF ou registro profissional pertence a pessoas reais, e nada aqui é orientação médica.

Esta página lista o que o seed cria e onde cada informação aparece nas telas. Os **nomes** de
profissionais, pacientes e medicamentos são sempre os mesmos (o gerador é determinístico). Já as
**quantidades, datas, estoques e quais pacientes têm alergias ou condições** dependem do dia em que
o seed rodou e dos registros que já existiam no banco, por isso não aparecem aqui: consulte-os na tela.

## Como carregar estes dados

- **No Render:** em *Environment*, defina `SEED_DEMO_DATA=True` e salve (o serviço reinicia em ~1 min).
- **No computador:** no `.env`, `SEED_DEMO_DATA=True`; ou rode `python -m scripts.seed_demo`.

O seed **só acrescenta** dados fictícios: não apaga nem altera os registros que já existem, e rodar de
novo não duplica nada. Para conferir, abra `/status` e veja o total de pacientes e profissionais.

## O que o seed cria

| Item | Quantidade |
|---|---:|
| Pacientes (somados aos já cadastrados) | 50 |
| Profissionais de saúde | 20 |
| Consultas (passadas e futuras) | 100 |
| Solicitações de exame | 200 |
| Prescrições | 150 |
| Medicamentos (com lotes e estoque) | 12 |
| Faturas (geradas das consultas e exames) | cerca de 60 |
| Alertas por regra | cerca de 80 |

## Médicos

No histórico de atividades: consultas, prescrições emitidas, exames solicitados e exames validados.

| Nome | Especialidade | Departamento | Registro (fictício) |
|---|---|---|---|
| Dr(a). Caio Moreira | Clínica Geral | Clínica Médica | CRM-PA 10001 |
| Dr(a). Enzo Cardoso | Pediatria | Pediatria | CRM-PA 10008 |
| Dr(a). Fernanda Pereira | Clínica Geral | Clínica Médica | CRM-PA 10003 |
| Dr(a). Igor Martins | Pediatria | Pediatria | CRM-PA 10007 |
| Dr(a). Lucas Pereira | Clínica Geral | Clínica Médica | CRM-PA 10002 |
| Dr(a). Paula Cardoso | Cardiologia | Cardiologia | CRM-PA 10005 |
| Dr(a). Vitória Santos | Cardiologia | Cardiologia | CRM-PA 10006 |
| Dr(a). William Dias | Endocrinologia | Clínica Médica | CRM-PA 10009 |
| Dr(a). William Rocha | Clínica Geral | Clínica Médica | CRM-PA 10004 |

## Enfermeiros

No histórico de atividades: registros de sinais vitais (cerca de 90 por enfermeiro, com o paciente de cada medição) e consultas de enfermagem.

| Nome | Especialidade | Departamento | Registro (fictício) |
|---|---|---|---|
| Enf. Débora Almeida | Enfermagem Clínica | Enfermagem | COREN-PA 10012 |
| Enf. Eduarda Cardoso | Enfermagem Clínica | Enfermagem | COREN-PA 10011 |
| Enf. Fernanda Martins | Enfermagem Clínica | Enfermagem | COREN-PA 10010 |

## Farmacêuticos

No histórico de atividades: dispensações de medicamentos (cerca de 45 por farmacêutico) e consultas.

| Nome | Especialidade | Departamento | Registro (fictício) |
|---|---|---|---|
| Farm. Bruno Cardoso | Farmácia Clínica | Farmácia | CRF-PA 10013 |
| Farm. Paula Martins | Farmácia Clínica | Farmácia | CRF-PA 10014 |

## Fisioterapeutas

No histórico de atividades: consultas.

| Nome | Especialidade | Departamento | Registro (fictício) |
|---|---|---|---|
| Fisio. Débora Dias | Fisioterapia | Reabilitação | CREFITO-PA 10016 |
| Fisio. Gustavo Cardoso | Fisioterapia | Reabilitação | CREFITO-PA 10015 |

## Psicólogos

No histórico de atividades: consultas.

| Nome | Especialidade | Departamento | Registro (fictício) |
|---|---|---|---|
| Psic. Igor Rodrigues | Psicologia Clínica | Saúde Mental | CRP-PA 10018 |
| Psic. Sofia Rodrigues | Psicologia Clínica | Saúde Mental | CRP-PA 10017 |

## Nutricionistas

No histórico de atividades: consultas.

| Nome | Especialidade | Departamento | Registro (fictício) |
|---|---|---|---|
| Nutri. Henrique Costa | Nutrição Clínica | Nutrição | CRN-PA 10019 |
| Nutri. Otávio Rocha | Nutrição Clínica | Nutrição | CRN-PA 10020 |

## Medicamentos

| Medicamento | Princípio ativo | Dose | Categoria |
|---|---|---|---|
| Amoxicilina Demo | Amoxicilina | 500mg | Antibióticos |
| Dexametasona Demo | Dexametasona | 4mg/ml | Corticoides |
| Dipirona Demo | Dipirona sódica | 500mg | Analgésicos e antitérmicos |
| Ibuprofeno Demo | Ibuprofeno | 400mg | Anti-inflamatórios |
| Insulina NPH Demo | Insulina humana NPH | 100UI/ml | Antidiabéticos |
| Losartana Demo | Losartana potássica | 50mg | Anti-hipertensivos |
| Metformina Demo | Metformina | 850mg | Antidiabéticos |
| Omeprazol Demo | Omeprazol | 20mg | Gastroprotetores |
| Paracetamol Demo | Paracetamol | 500mg | Analgésicos e antitérmicos |
| Salbutamol Demo | Salbutamol | 100mcg | Broncodilatadores |
| Sinvastatina Demo | Sinvastatina | 20mg | Hipolipemiantes |
| Soro Fisiológico Demo | Cloreto de sódio 0,9% | 500ml | Soluções e hidratação |

Estoque, lotes e validades estão em **Atendimento → Farmácia**. Alguns lotes são criados de propósito
vencidos ou perto do vencimento, e alguns itens abaixo do estoque mínimo, para os alertas da farmácia.

## Pacientes

O seed cria 50 pacientes. Todos têm sinais vitais e linha do tempo; muitos também
têm consultas, exames, prescrições e faturas. Nomes (em ordem alfabética):

- Ana Ribeiro Costa · Ana Rodrigues Nascimento · Beatriz Araújo Carvalho · Beatriz Carvalho Rocha · Beatriz Costa Rocha
- Beatriz Dias Ribeiro · Bruno Rodrigues Barbosa · Caio Dias Barbosa · Caio Lima Dias · Carla Araújo Silva
- Carla Pereira Dias · Carla Souza Moreira · Daniel Barbosa Gomes · Daniel Rocha Carvalho · Débora Oliveira Nascimento
- Débora Santos Dias · Eduarda Moreira Ribeiro · Eduarda Nascimento Moreira · Enzo Carvalho Martins · Enzo Nascimento Santos
- Enzo Silva Pereira · Felipe Almeida Dias · Felipe Martins Ribeiro · Fernanda Nascimento Araújo · Gustavo Almeida Souza
- Gustavo Nascimento Lima · Helena Gomes Gomes · Helena Oliveira Gomes · Igor Barbosa Cardoso · Igor Lima Barbosa
- João Moreira Costa · João Ribeiro Moreira · João Ribeiro Santos · Júlia Lima Almeida · Júlia Nascimento Rocha
- Júlia Silva Araújo · Larissa Cardoso Ribeiro · Larissa Carvalho Gomes · Larissa Costa Cardoso · Larissa Pereira Silva
- Larissa Rocha Araújo · Lucas Araújo Pereira · Lucas Rocha Barbosa · Marcos Almeida Dias · Marcos Martins Ribeiro
- Paula Costa Gomes · Sofia Gomes Barbosa · William Barbosa Souza · William Rodrigues Costa · William Silva Nascimento

**Para achar bons exemplos na tela:**

- **Paciente com exame alterado:** *Gestão → Alertas* → categoria *Laboratorial* → o alerta aponta o paciente.
- **Paciente com alergias e condições:** *Atendimento → Prontuário* → abra pacientes da lista; as alergias
  aparecem em destaque no cabeçalho do prontuário.
- **Paciente com fatura em atraso:** *Gestão → Financeiro* → filtre *Em atraso* → abra a fatura.
- **Qualquer nome acima:** digite parte dele na busca (tecla `/`).

## Onde ver cada histórico

| Quero ver… | Caminho na tela |
|---|---|
| **Histórico de um médico** | **Gestão → Profissionais** → filtre *Médico(a)* → clique no nome → *Histórico de atividades* (consultas, prescrições, exames). A agenda fica em *Ver agenda*. |
| **Histórico de um enfermeiro** | **Gestão → Profissionais** → filtre *Enfermeiro(a)* → clique no nome → *Histórico de atividades* (sinais vitais registrados, com o paciente de cada medição). |
| **Histórico de um farmacêutico** | **Gestão → Profissionais** → filtre *Farmacêutico(a)* → clique no nome → *Histórico de atividades* (dispensações). |
| **Histórico de um paciente** | **Atendimento → Prontuário** → escolha o paciente → aba *Linha do tempo* (consultas, exames, prescrições, sinais vitais, diagnósticos). As abas *Sinais vitais* e *Exames* têm gráficos de evolução. |
| **Histórico de um remédio** | **Atendimento → Farmácia** → aba *Movimentações* (entradas, dispensações e descartes por lote) e aba *Validade* (lotes vencidos ou vencendo). |
| **Painel geral** | **Painel**: troque o perfil no topo (*Administração*, *Farmácia*, um profissional ou um paciente) para ver cada visão. |
| **Financeiro** | **Gestão → Financeiro**: faturas pagas, em aberto e em atraso, geradas a partir das consultas e exames. |

Também pela API (`/docs`): `GET /api/v1/professionals/{id}/activity`, `GET /api/v1/patients/{id}/timeline`,
`GET /api/v1/stock/movements?medication_id=...`.
