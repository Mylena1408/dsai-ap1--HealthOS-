from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import uuid
from datetime import datetime

class MedicationUnit(Enum):
    """Unidades de medida para medicamentos e suprimentos."""
    TABLET = "COMPRIMIDO"
    MILLILITER = "ML"
    AMPOULE = "AMPOLA"
    VIAL = "FRASCO-AMPOLA"
    UNIT = "UNIDADE"
    DROP = "GOTA"

class StockStatus(Enum):
    """Status do nível de estoque."""
    IN_STOCK = "EM_ESTOQUE"
    LOW_STOCK = "ESTOQUE_BAIXO"
    OUT_OF_STOCK = "ESGOTADO"

@dataclass
class Medication:
    """
    Entidade de Domínio Medication.
    Representa um medicamento cadastrado no sistema hospitalar.
    """
    id: Optional[uuid.UUID] = None
    name: str = field(default="")
    generic_name: str = field(default="")
    dosage: str = field(default="")
    unit: MedicationUnit = field(default=MedicationUnit.UNIT)
    is_controlled_substance: bool = False
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.name:
            raise ValueError("O nome do medicamento é obrigatório.")

@dataclass
class InventoryItem:
    """
    Entidade de Domínio InventoryItem.
    Representa a quantidade física de um medicamento em um local específico.
    """
    id: Optional[uuid.UUID] = None
    medication_id: uuid.UUID = field(default=None)
    location_id: uuid.UUID = field(default=None) # Ex: Farmácia Central, Ala A, UTI
    quantity: float = 0.0
    min_threshold: float = 10.0 # Gatilho para alerta de estoque baixo
    max_threshold: float = 1000.0
    expiration_date: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)

    def calculate_status(self) -> StockStatus:
        """Determina o status do estoque com base nos limiares."""
        if self.quantity <= 0:
            return StockStatus.OUT_OF_STOCK
        if self.quantity <= self.min_threshold:
            return StockStatus.LOW_STOCK
        return StockStatus.IN_STOCK

    def add_stock(self, amount: float):
        """Adiciona quantidade ao estoque."""
        if amount < 0:
            raise ValueError("A quantidade a adicionar deve ser positiva.")
        self.quantity += amount
        self.last_updated = datetime.now()

    def remove_stock(self, amount: float):
        """Remove quantidade do estoque, validando disponibilidade."""
        if amount < 0:
            raise ValueError("A quantidade a remover deve ser positiva.")
        if self.quantity < amount:
            raise ValueError("Quantidade insuficiente em estoque.")
        self.quantity -= amount
        self.last_updated = datetime.now()
