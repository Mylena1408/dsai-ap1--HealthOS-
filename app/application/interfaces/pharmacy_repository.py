from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
import uuid

from app.domain.entities.medication import Medication
from app.domain.entities.pharmacy import (
    Dispensation, InventoryMovement, MedicationCategory, MedicationDetails, MovementType, Prescription,
    PrescriptionStatus, StockLot,
)


@dataclass
class LotFilters:
    medication_id: Optional[uuid.UUID] = None
    location: Optional[str] = None
    expiring_before: Optional[date] = None  # inclui lotes já vencidos
    include_empty: bool = False
    limit: int = 50
    offset: int = 0


@dataclass
class MovementFilters:
    medication_id: Optional[uuid.UUID] = None
    location: Optional[str] = None
    movement_type: Optional[MovementType] = None
    reference_id: Optional[uuid.UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


@dataclass
class PrescriptionFilters:
    patient_id: Optional[uuid.UUID] = None
    prescriber_id: Optional[uuid.UUID] = None
    statuses: list[PrescriptionStatus] = field(default_factory=list)
    date_from: Optional[datetime] = None
    limit: int = 20
    offset: int = 0


@dataclass
class StockRow:
    """Posição consolidada de um medicamento (somando todos os locais)."""
    medication: Medication
    details: Optional[MedicationDetails]
    total: float
    lotted: float
    below_minimum_locations: int
    nearest_expiration: Optional[date]


class PharmacyRepository(ABC):
    # catálogo
    @abstractmethod
    async def list_categories(self) -> list[MedicationCategory]: ...
    @abstractmethod
    async def get_category(self, category_id: uuid.UUID) -> Optional[MedicationCategory]: ...
    @abstractmethod
    async def get_category_by_name(self, name: str) -> Optional[MedicationCategory]: ...
    @abstractmethod
    async def save_category(self, category: MedicationCategory) -> MedicationCategory: ...
    @abstractmethod
    async def get_details(self, medication_id: uuid.UUID) -> Optional[MedicationDetails]: ...
    @abstractmethod
    async def save_details(self, details: MedicationDetails) -> MedicationDetails: ...
    @abstractmethod
    async def medications_by_ids(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, Medication]: ...
    @abstractmethod
    async def patient_names(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]: ...
    @abstractmethod
    async def stock_overview(self, query: Optional[str], category_id: Optional[uuid.UUID],
                             low_stock_only: bool) -> list[StockRow]: ...

    # lotes e movimentações
    @abstractmethod
    async def save_lot(self, lot: StockLot) -> StockLot: ...
    @abstractmethod
    async def get_lot(self, lot_id: uuid.UUID) -> Optional[StockLot]: ...
    @abstractmethod
    async def find_lot(self, medication_id: uuid.UUID, location: str, lot_number: str) -> Optional[StockLot]: ...
    @abstractmethod
    async def lots_for(self, medication_id: uuid.UUID, location: str) -> list[StockLot]: ...
    @abstractmethod
    async def search_lots(self, filters: LotFilters) -> tuple[list[StockLot], int]: ...
    @abstractmethod
    async def add_movement(self, movement: InventoryMovement) -> InventoryMovement: ...
    @abstractmethod
    async def search_movements(self, filters: MovementFilters) -> tuple[list[InventoryMovement], int]: ...

    # prescrições e dispensações
    @abstractmethod
    async def save_prescription(self, prescription: Prescription) -> Prescription: ...
    @abstractmethod
    async def get_prescription(self, prescription_id: uuid.UUID) -> Optional[Prescription]: ...
    @abstractmethod
    async def search_prescriptions(self, filters: PrescriptionFilters) -> tuple[list[Prescription], int]: ...
    @abstractmethod
    async def save_dispensation(self, dispensation: Dispensation) -> Dispensation: ...
    @abstractmethod
    async def list_dispensations(self, prescription_id: Optional[uuid.UUID] = None,
                                 patient_id: Optional[uuid.UUID] = None,
                                 limit: int = 50, offset: int = 0) -> tuple[list[Dispensation], int]: ...
