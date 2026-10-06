from datetime import date, datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field

from app.domain.entities.pharmacy import (
    AdministrationRoute, CatalogStatus, ItemStatus, MovementType, PrescriptionStatus,
)


# ---------------------------------------------------------------------- catálogo

class CategoryCreateDTO(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    description: Optional[str] = Field(None, max_length=500)


class CategoryDTO(CategoryCreateDTO):
    id: uuid.UUID


class MedicationDetailsDTO(BaseModel):
    category_id: Optional[uuid.UUID] = None
    catalog_status: CatalogStatus = CatalogStatus.ACTIVE
    requires_prescription: bool = True


class StockOverviewDTO(BaseModel):
    medication_id: uuid.UUID
    name: str
    generic_name: str
    dosage: str
    unit: str
    is_controlled: bool
    category_id: Optional[uuid.UUID]
    category_name: Optional[str]
    catalog_status: CatalogStatus
    total_quantity: float
    lotted_quantity: float
    unlotted_quantity: float
    below_minimum_locations: int
    nearest_expiration: Optional[date]


# ------------------------------------------------------------------------- estoque

class LotReceiveDTO(BaseModel):
    medication_id: uuid.UUID
    location: str = Field(..., min_length=2, max_length=100)
    lot_number: str = Field(..., min_length=1, max_length=40)
    expiration_date: date
    quantity: float = Field(..., gt=0, le=100000)


class LotDTO(BaseModel):
    id: uuid.UUID
    medication_id: uuid.UUID
    medication_name: Optional[str]
    location: str
    lot_number: str
    expiration_date: date
    days_to_expire: int
    is_expired: bool
    quantity: float
    received_at: datetime


class DiscardDTO(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class MovementDTO(BaseModel):
    id: uuid.UUID
    medication_id: uuid.UUID
    medication_name: Optional[str]
    location: str
    movement_type: MovementType
    quantity: float
    balance_after: float
    lot_id: Optional[uuid.UUID]
    reference_id: Optional[uuid.UUID]
    reason: Optional[str]
    occurred_at: datetime


# ---------------------------------------------------------------------- prescrição

class PrescriptionItemCreateDTO(BaseModel):
    medication_id: uuid.UUID
    dose: str = Field(..., min_length=1, max_length=100)
    frequency: str = Field(..., min_length=1, max_length=100)
    duration_days: int = Field(..., ge=1, le=365)
    quantity: float = Field(..., gt=0)
    route: AdministrationRoute = AdministrationRoute.ORAL
    instructions: Optional[str] = Field(None, max_length=500)


class PrescriptionCreateDTO(BaseModel):
    patient_id: uuid.UUID
    prescriber_id: uuid.UUID
    appointment_id: Optional[uuid.UUID] = None
    items: list[PrescriptionItemCreateDTO] = Field(..., min_length=1, max_length=20)
    notes: Optional[str] = Field(None, max_length=2000)
    allergy_override_reason: Optional[str] = Field(
        None, max_length=500, description="Obrigatória para prescrever apesar de alergia registrada")


class ReasonDTO(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class PrescriptionItemDTO(BaseModel):
    id: uuid.UUID
    medication_id: uuid.UUID
    medication_name: Optional[str]
    dose: str
    frequency: str
    duration_days: int
    route: AdministrationRoute
    quantity: float
    dispensed_quantity: float
    remaining_quantity: float
    instructions: Optional[str]
    status: ItemStatus
    status_reason: Optional[str]


class PrescriptionDTO(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: Optional[str]
    prescriber_id: uuid.UUID
    prescriber_name: Optional[str]
    appointment_id: Optional[uuid.UUID]
    issued_at: datetime
    valid_until: datetime
    is_expired: bool
    status: PrescriptionStatus
    special_control: bool
    allergy_override_reason: Optional[str]
    notes: Optional[str]
    cancellation_reason: Optional[str]
    items: list[PrescriptionItemDTO]


class PatientMedicationDTO(BaseModel):
    """Visão de 'medicamentos do paciente' a partir dos itens prescritos."""
    prescription_id: uuid.UUID
    item_id: uuid.UUID
    medication_name: Optional[str]
    dose: str
    frequency: str
    route: AdministrationRoute
    status: ItemStatus
    status_reason: Optional[str]
    issued_at: datetime
    prescriber_name: Optional[str]
    dispensed_quantity: float
    quantity: float


# --------------------------------------------------------------------- dispensação

class DispensationItemDTO(BaseModel):
    prescription_item_id: uuid.UUID
    quantity: float = Field(..., gt=0)


class DispensationCreateDTO(BaseModel):
    prescription_id: uuid.UUID
    pharmacist_id: uuid.UUID
    location: str = Field(..., min_length=2, max_length=100)
    items: list[DispensationItemDTO] = Field(..., min_length=1)
    notes: Optional[str] = Field(None, max_length=500)


class DispensationLineDTO(BaseModel):
    prescription_item_id: uuid.UUID
    medication_id: uuid.UUID
    medication_name: Optional[str]
    lot_id: Optional[uuid.UUID]
    lot_number: Optional[str]
    quantity: float


class DispensationDTO(BaseModel):
    id: uuid.UUID
    prescription_id: uuid.UUID
    patient_id: uuid.UUID
    pharmacist_id: uuid.UUID
    pharmacist_name: Optional[str]
    location: str
    dispensed_at: datetime
    notes: Optional[str]
    lines: list[DispensationLineDTO]
    prescription_status: Optional[PrescriptionStatus] = None
