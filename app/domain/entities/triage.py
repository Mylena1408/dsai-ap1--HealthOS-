from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
import uuid

class TriagePriority(Enum):
    """
    Classificação de Risco baseada no Protocolo de Manchester.
    """
    RED = ("EMERGÊNCIA", 0)     # Atendimento imediato
    ORANGE = ("MUITO URGENTE", 1) # Atendimento em até 10 min
    YELLOW = ("URGENTE", 2)      # Atendimento em até 60 min
    GREEN = ("POUCO URGENTE", 3)  # Atendimento em até 120 min
    BLUE = ("NÃO URGENTE", 4)     # Atendimento em até 240 min

    def __init__(self, label: str, level: int):
        self.label = label
        self.level = level

@dataclass
class Triage:
    """
    Entidade de Domínio Triage.
    Representa a avaliação inicial do paciente ao entrar na unidade de saúde.
    """
    id: Optional[uuid.UUID] = None
    patient_id: uuid.UUID = field(default=None)
    triage_nurse_id: uuid.UUID = field(default=None)
    priority: TriagePriority = field(default=TriagePriority.BLUE)

    # Sinais Vitais
    blood_pressure: str = field(default="0/0")
    heart_rate: int = field(default=0)
    temperature: float = field(default=0.0)
    oxygen_saturation: int = field(default=0)
    respiratory_rate: int = field(default=0)

    # Avaliação
    main_complaint: str = field(default="")
    observations: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self.validate_vitals()

    def validate_vitals(self):
        """Validações básicas de sinais vitais para evitar dados impossíveis."""
        if not (0 <= self.oxygen_saturation <= 100):
            raise ValueError("Saturação de oxigênio deve estar entre 0 e 100%.")

        if not (0 <= self.heart_rate <= 300):
            raise ValueError("Frequência cardíaca fora dos limites fisiológicos aceitáveis.")

        if not (20 <= self.temperature <= 45):
            raise ValueError("Temperatura corporal fora dos limites aceitáveis.")

    def update_priority(self, new_priority: TriagePriority):
        """Permite reclassificar o paciente caso o quadro clínico evolua."""
        self.priority = new_priority
        self.updated_at = datetime.now()
