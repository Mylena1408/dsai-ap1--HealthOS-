# Dados de exemplo do HealthOS

> **Todos os dados abaixo são fictícios**, gerados automaticamente pelo seed de demonstração. Nenhum
> nome, CPF ou registro profissional pertence a pessoas reais, e nada aqui é orientação médica.

Esta página mostra o que existe no sistema depois que os dados de demonstração são carregados e
onde cada informação aparece nas telas. Os nomes são sempre os mesmos, porque o gerador é
determinístico. As datas são relativas ao dia em que o seed rodou, então mudam de um ambiente para outro.

## Como carregar estes dados

- **No Render:** em *Environment*, defina `SEED_DEMO_DATA=True` e salve (o serviço reinicia).
- **No computador:** no `.env`, `SEED_DEMO_DATA=True`; ou rode `python -m scripts.seed_demo`.

O seed é idempotente: rodar de novo não duplica nem apaga registros.

## Visão geral

| Item | Quantidade |
|---|---:|
| Pacientes | 50 |
| Profissionais de saúde | 20 |
| Consultas | 100 |
| Medicamentos | 12 |
| Faturas | 64 |
| Health Score médio dos pacientes | 61,7 |

## Médicos

| Nome | Especialidade | Registro (fictício) | Histórico registrado |
|---|---|---|---|
| Dr(a). Caio Moreira | Clínica Geral | CRM-PA 10001 | 27 exames solicitados, 12 prescrições, 9 exames validados, 5 consultas |
| Dr(a). Enzo Cardoso | Pediatria | CRM-PA 10008 | 18 prescrições, 17 exames solicitados, 10 exames validados, 5 consultas |
| Dr(a). Fernanda Pereira | Clínica Geral | CRM-PA 10003 | 21 exames solicitados, 15 prescrições, 13 exames validados, 2 consultas |
| Dr(a). Igor Martins | Pediatria | CRM-PA 10007 | 17 exames solicitados, 15 prescrições, 13 exames validados, 5 consultas |
| Dr(a). Lucas Pereira | Clínica Geral | CRM-PA 10002 | 21 exames solicitados, 19 prescrições, 16 exames validados, 5 consultas |
| Dr(a). Paula Cardoso | Cardiologia | CRM-PA 10005 | 19 exames solicitados, 17 exames validados, 15 prescrições, 2 consultas |
| Dr(a). Vitória Santos | Cardiologia | CRM-PA 10006 | 27 exames solicitados, 21 prescrições, 11 exames validados, 2 consultas |
| Dr(a). William Dias | Endocrinologia | CRM-PA 10009 | 28 exames solicitados, 17 prescrições, 5 exames validados |
| Dr(a). William Rocha | Clínica Geral | CRM-PA 10004 | 23 exames solicitados, 18 prescrições, 7 exames validados, 3 consultas |

## Enfermeiros

| Nome | Especialidade | Registro (fictício) | Histórico registrado |
|---|---|---|---|
| Enf. Débora Almeida | Enfermagem Clínica | COREN-PA 10012 | 93 registros de sinais vitais, 6 consultas |
| Enf. Eduarda Cardoso | Enfermagem Clínica | COREN-PA 10011 | 93 registros de sinais vitais, 6 consultas |
| Enf. Fernanda Martins | Enfermagem Clínica | COREN-PA 10010 | 92 registros de sinais vitais, 2 consultas |

## Farmacêuticos

| Nome | Especialidade | Registro (fictício) | Histórico registrado |
|---|---|---|---|
| Farm. Bruno Cardoso | Farmácia Clínica | CRF-PA 10013 | 45 dispensações, 1 consulta |
| Farm. Paula Martins | Farmácia Clínica | CRF-PA 10014 | 46 dispensações, 2 consultas |

## Fisioterapeutas

| Nome | Especialidade | Registro (fictício) | Histórico registrado |
|---|---|---|---|
| Fisio. Débora Dias | Fisioterapia | CREFITO-PA 10016 | 2 consultas |
| Fisio. Gustavo Cardoso | Fisioterapia | CREFITO-PA 10015 | 3 consultas |

## Psicólogos

| Nome | Especialidade | Registro (fictício) | Histórico registrado |
|---|---|---|---|
| Psic. Igor Rodrigues | Psicologia Clínica | CRP-PA 10018 | 2 consultas |
| Psic. Sofia Rodrigues | Psicologia Clínica | CRP-PA 10017 | 3 consultas |

## Nutricionistas

| Nome | Especialidade | Registro (fictício) | Histórico registrado |
|---|---|---|---|
| Nutri. Henrique Costa | Nutrição Clínica | CRN-PA 10019 | 5 consultas |
| Nutri. Otávio Rocha | Nutrição Clínica | CRN-PA 10020 | 4 consultas |

## Medicamentos

| Medicamento | Princípio ativo | Dose | Categoria | Estoque (un.) | Validade mais próxima |
|---|---|---|---|---:|---|
| Amoxicilina Demo | Amoxicilina | 500mg | Antibióticos | 905 | 01/10/2026 |
| Dexametasona Demo | Dexametasona | 4mg/ml | Corticoides | 129 | 18/10/2026 |
| Dipirona Demo | Dipirona sódica | 500mg | Analgésicos e antitérmicos | 795 | 18/10/2026 |
| Ibuprofeno Demo | Ibuprofeno | 400mg | Anti-inflamatórios | 966 | 01/10/2026 |
| Insulina NPH Demo | Insulina humana NPH | 100UI/ml | Antidiabéticos | 618 | 01/10/2026 |
| Losartana Demo | Losartana potássica | 50mg | Anti-hipertensivos | 998 | 01/10/2026 |
| Metformina Demo | Metformina | 850mg | Antidiabéticos | 923 | 01/10/2026 |
| Omeprazol Demo | Omeprazol | 20mg | Gastroprotetores | 813 | 31/10/2026 |
| Paracetamol Demo | Paracetamol | 500mg | Analgésicos e antitérmicos | 797 | 01/10/2026 |
| Salbutamol Demo | Salbutamol | 100mcg | Broncodilatadores | 719 | 01/10/2026 |
| Sinvastatina Demo | Sinvastatina | 20mg | Hipolipemiantes | 865 | 01/10/2026 |
| Soro Fisiológico Demo | Cloreto de sódio 0,9% | 500ml | Soluções e hidratação | 240 | 18/10/2026 |

Alguns lotes estão de propósito vencidos ou perto do vencimento, e alguns itens abaixo do estoque
mínimo, para que os alertas da farmácia tenham o que mostrar.

## Pacientes para a demonstração

Os cinco pacientes com o histórico mais completo:

| Paciente | Idade | Alergias | Condições ativas | Eventos na linha do tempo | Health Score |
|---|---:|---|---|---:|---|
| Igor Lima Barbosa | 67 | Ácaros, Dipirona | Dislipidemia, Hipertensão arterial | 35 | 68 (Atenção) |
| Ana Rodrigues Nascimento | 21 | Penicilina, Lactose | Asma, Rinite alérgica | 32 | 71 (Atenção) |
| Fernanda Nascimento Araújo | 26 | Lactose | Lombalgia crônica, Rinite alérgica | 34 | 79 (Atenção) |
| Caio Lima Dias | 63 | Camarão, Ácaros | Hipotireoidismo | 33 | 71 (Atenção) |
| Beatriz Araújo Carvalho | 27 | — | Rinite alérgica | 36 | 89 (Bom) |

Para encontrar um deles, digite parte do nome na busca (tecla `/`) ou em **Atendimento → Prontuário**.

## Onde ver cada histórico

| Quero ver… | Caminho na tela |
|---|---|
| **Histórico de um médico** | **Gestão → Profissionais** → filtre *Médico* → clique no nome → *Histórico de atividades* (consultas, prescrições, exames). A agenda fica em *Ver agenda*. |
| **Histórico de um enfermeiro** | **Gestão → Profissionais** → filtre *Enfermeiro* → clique no nome → *Histórico de atividades* (sinais vitais registrados, com o paciente de cada medição). |
| **Histórico de um farmacêutico** | **Gestão → Profissionais** → filtre *Farmacêutico* → clique no nome → dispensações realizadas. |
| **Histórico de um paciente** | **Atendimento → Prontuário** → escolha o paciente → aba *Linha do tempo* (consultas, exames, prescrições, sinais vitais, diagnósticos). As abas *Sinais vitais* e *Exames* têm gráficos de evolução. |
| **Histórico de um remédio** | **Atendimento → Farmácia** → aba *Movimentações* (entradas, dispensações e descartes por lote) e aba *Validade* (lotes vencidos ou vencendo). |
| **Painel geral** | **Painel**: troque o perfil no topo (*Administração*, *Farmácia*, um profissional ou um paciente) para ver cada visão. |
| **Financeiro** | **Gestão → Financeiro**: faturas pagas, em aberto e em atraso, geradas a partir das consultas e exames. |

Também pela API (`/docs`): `GET /api/v1/professionals/{id}/activity`, `GET /api/v1/patients/{id}/timeline`,
`GET /api/v1/stock/movements?medication_id=...`.
