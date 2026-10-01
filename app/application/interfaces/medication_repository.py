from abc import ABC, abstractmethod
from typing import List, Optional
import uuid
from app.domain.entities.medication import Medication, InventoryItem

class MedicationRepository(ABC):
    """
    Interface de Repositório para Medicamentos.
    """

    @abstractmethod
    async def save(self, medication: Medication) -> Medication:
        pass

    @abstractmethod
    async def get_by_id(self, medication_id: uuid.UUID) -> Optional[Medication]:
        pass

    @abstractmethod
    async def list_all(self) -> List[Medication]:
        pass

    @abstractmethod
    async def search_by_name(self, name: str) -> List[Medication]:
        pass

class InventoryRepository(ABC):
    """
    Interface de Repositório para Itens de Inventário.
    """

    @abstractmethod
    async def save(self, item: InventoryItem) -> InventoryItem:
        pass

    @abstractmethod
    async def get_by_medication_and_location(self, medication_id: uuid.UUID, location_id: uuid.UUID) -> Optional[InventoryItem]:
        pass

    @abstractmethod
    async def update_quantity(self, item_id: uuid.UUID, new_quantity: float) -> InventoryItem:
        pass

    @abstractmethod
    async def get_low_stock_items(self) -> List[InventoryItem]:
        pass
