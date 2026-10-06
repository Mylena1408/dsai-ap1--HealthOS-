"""Geradores determinísticos de dados FICTÍCIOS para demonstração.

Nada aqui representa pessoas reais: nomes são combinações aleatórias, CPFs são
gerados apenas com dígitos verificadores válidos e e-mails usam o domínio
reservado example.com (RFC 2606).
"""
import random
import unicodedata
from datetime import date, timedelta

FIRST_NAMES = [
    "Ana", "Bruno", "Carla", "Daniel", "Eduarda", "Felipe", "Gabriela", "Henrique", "Isabela", "João",
    "Larissa", "Marcos", "Natália", "Otávio", "Paula", "Rafael", "Sofia", "Tiago", "Vitória", "William",
    "Beatriz", "Caio", "Débora", "Enzo", "Fernanda", "Gustavo", "Helena", "Igor", "Júlia", "Lucas",
]
LAST_NAMES = [
    "Silva", "Souza", "Oliveira", "Santos", "Lima", "Pereira", "Costa", "Rodrigues", "Almeida", "Nascimento",
    "Carvalho", "Gomes", "Martins", "Araújo", "Ribeiro", "Barbosa", "Rocha", "Dias", "Moreira", "Cardoso",
]
STREETS = ["Rua das Acácias", "Av. dos Ipês", "Travessa do Açaí", "Rua do Cupuaçu", "Av. Central", "Rua das Mangueiras"]
DISTRICTS = ["Bairro Fictício", "Vila Exemplo", "Jardim Demonstração", "Centro Didático"]
INSURANCES = ["Convênio Fictício Saúde", "Plano Demo Vida", "Assistência Exemplo", None, None]
GENDERS = ["Feminino", "Masculino", "Outro"]

# Catálogo fictício inspirado em nomes genéricos comuns; dosagens ilustrativas.
MEDICATIONS = [
    ("Paracetamol Demo", "Paracetamol", "500mg", "COMPRIMIDO"),
    ("Dipirona Demo", "Dipirona sódica", "500mg", "COMPRIMIDO"),
    ("Ibuprofeno Demo", "Ibuprofeno", "400mg", "COMPRIMIDO"),
    ("Amoxicilina Demo", "Amoxicilina", "500mg", "COMPRIMIDO"),
    ("Omeprazol Demo", "Omeprazol", "20mg", "COMPRIMIDO"),
    ("Losartana Demo", "Losartana potássica", "50mg", "COMPRIMIDO"),
    ("Metformina Demo", "Metformina", "850mg", "COMPRIMIDO"),
    ("Sinvastatina Demo", "Sinvastatina", "20mg", "COMPRIMIDO"),
    ("Soro Fisiológico Demo", "Cloreto de sódio 0,9%", "500ml", "ML"),
    ("Dexametasona Demo", "Dexametasona", "4mg/ml", "AMPOLA"),
    ("Insulina NPH Demo", "Insulina humana NPH", "100UI/ml", "FRASCO-AMPOLA"),
    ("Salbutamol Demo", "Salbutamol", "100mcg", "UNIDADE"),
]
STOCK_LOCATIONS = ["FARMACIA_CENTRAL", "ALA_A", "PRONTO_ATENDIMENTO"]

DEPARTMENTS = [
    ("Clínica Médica", "Atendimento ambulatorial geral."),
    ("Cardiologia", "Acompanhamento cardiovascular."),
    ("Pediatria", "Atendimento a crianças e adolescentes."),
    ("Enfermagem", "Procedimentos e acompanhamento de enfermagem."),
    ("Farmácia", "Dispensação e controle de medicamentos."),
    ("Reabilitação", "Fisioterapia e terapias de apoio."),
    ("Saúde Mental", "Psicologia e acolhimento."),
    ("Nutrição", "Orientação alimentar."),
]

# (especialidade, duração padrão em minutos, departamento)
SPECIALTIES = [
    ("Clínica Geral", 30, "Clínica Médica"),
    ("Cardiologia", 40, "Cardiologia"),
    ("Pediatria", 30, "Pediatria"),
    ("Endocrinologia", 40, "Clínica Médica"),
    ("Enfermagem Clínica", 20, "Enfermagem"),
    ("Farmácia Clínica", 20, "Farmácia"),
    ("Fisioterapia", 50, "Reabilitação"),
    ("Psicologia Clínica", 50, "Saúde Mental"),
    ("Nutrição Clínica", 40, "Nutrição"),
]

# (tipo de profissional, especialidade, quantidade)
PROFESSIONAL_MIX = [
    ("MEDICO", "Clínica Geral", 4), ("MEDICO", "Cardiologia", 2), ("MEDICO", "Pediatria", 2),
    ("MEDICO", "Endocrinologia", 1), ("ENFERMEIRO", "Enfermagem Clínica", 3),
    ("FARMACEUTICO", "Farmácia Clínica", 2), ("FISIOTERAPEUTA", "Fisioterapia", 2),
    ("PSICOLOGO", "Psicologia Clínica", 2), ("NUTRICIONISTA", "Nutrição Clínica", 2),
]

# Turnos de atendimento possíveis (início, fim) em horas.
SHIFTS = [(8, 12), (13, 17), (8, 17)]

APPOINTMENT_REASONS = [
    "Consulta de rotina", "Retorno com exames", "Acompanhamento de tratamento",
    "Avaliação inicial", "Renovação de receita", "Orientações gerais",
]


def fake_professional_name(rng: random.Random, title: str) -> str:
    return f"{title} {rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _cpf_digit(digits: list[int]) -> int:
    weight = len(digits) + 1
    remainder = sum(d * (weight - i) for i, d in enumerate(digits)) % 11
    return 0 if remainder < 2 else 11 - remainder


def generate_cpf(rng: random.Random) -> str:
    """CPF fictício com dígitos verificadores válidos (somente números)."""
    while True:
        base = [rng.randint(0, 9) for _ in range(9)]
        if len(set(base)) > 1:
            break
    first = _cpf_digit(base)
    second = _cpf_digit(base + [first])
    return "".join(map(str, base + [first, second]))


def is_valid_cpf(cpf: str) -> bool:
    digits = [int(c) for c in cpf if c.isdigit()]
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    return _cpf_digit(digits[:9]) == digits[9] and _cpf_digit(digits[:10]) == digits[10]


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return ascii_text.lower().replace(" ", ".")


def fake_patient(rng: random.Random, today: date | None = None) -> dict:
    today = today or date.today()
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    full_name = f"{first} {rng.choice(LAST_NAMES)} {last}"
    insurance = rng.choice(INSURANCES)
    return {
        "full_name": full_name,
        "cpf": generate_cpf(rng),
        "birth_date": today - timedelta(days=rng.randint(18 * 365, 90 * 365)),
        "gender": rng.choice(GENDERS),
        "phone": f"(91) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
        "email": f"{_slug(first)}.{_slug(last)}{rng.randint(1, 999)}@example.com",
        "address": f"{rng.choice(STREETS)}, {rng.randint(1, 999)} - {rng.choice(DISTRICTS)}",
        "insurance_provider": insurance,
        "insurance_number": f"DEMO-{rng.randint(100000, 999999)}" if insurance else None,
    }
