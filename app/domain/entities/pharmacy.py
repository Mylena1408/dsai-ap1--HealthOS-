"""Farmácia didática: categorias, lotes, movimentações, prescrições e dispensações.

Fluxo:  consulta ─► prescrição ─► farmácia ─► dispensação ─► baixa no estoque (FEFO)

Prescrição:  ATIVA ─► PARCIALMENTE_DISPENSADA ─► DISPENSADA
               └──────────────┴─────────────────► CANCELADA
Item:        EM_USO ⇄ SUSPENSO ;  EM_USO ─► CONCLUIDO
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional
import uuid

from app.domain.exceptions.common import BusinessRuleViolation, ConflictError, InvalidTransitionError

PRESCRIPTION_VALIDITY_DAYS = 30
CONTROLLED_MAX_QUANTITY = 60
MAX_ITEM_QUANTITY = 1000


# --------------------------------------------------------------------- catálogo

class CatalogStatus(Enum):
    ACTIVE = "ATIVO"
    DISCONTINUED = "DESCONTINUADO"


@dataclass
class MedicationCategory:
    name: str
    description: Optional[str] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        if len(self.name.strip()) < 3:
            raise BusinessRuleViolation("O nome da categoria deve ter pelo menos 3 caracteres.")


@dataclass
class MedicationDetails:
    """Dados complementares de um medicamento do catálogo legado (1:1)."""
    medication_id: uuid.UUID
    category_id: Optional[uuid.UUID] = None
    catalog_status: CatalogStatus = CatalogStatus.ACTIVE
    requires_prescription: bool = True


# ------------------------------------------------------------------------ estoque

class MovementType(Enum):
    RECEIPT = "ENTRADA"
    DISPENSATION = "DISPENSACAO"
    ADJUSTMENT = "AJUSTE"
    DISPOSAL = "DESCARTE"


@dataclass
class StockLot:
    medication_id: uuid.UUID
    location: str
    lot_number: str
    expiration_date: date
    quantity: float
    received_at: datetime
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        self.lot_number = self.lot_number.strip().upper()
        if not self.lot_number:
            raise BusinessRuleViolation("O número do lote é obrigatório.")
        if self.quantity < 0:
            raise BusinessRuleViolation("A quantidade do lote não pode ser negativa.")

    def is_expired(self, today: date) -> bool:
        return self.expiration_date < today

    def take(self, amount: float) -> None:
        if amount <= 0 or amount > self.quantity:
            raise BusinessRuleViolation(f"Quantidade inválida para o lote {self.lot_number}.")
        self.quantity -= amount


@dataclass
class InventoryMovement:
    medication_id: uuid.UUID
    location: str
    movement_type: MovementType
    quantity: float  # sempre positiva; o tipo indica entrada ou saída
    occurred_at: datetime
    balance_after: float
    lot_id: Optional[uuid.UUID] = None
    reference_id: Optional[uuid.UUID] = None  # ex.: id da dispensação
    reason: Optional[str] = None
    id: Optional[uuid.UUID] = None

    @property
    def is_inbound(self) -> bool:
        return self.movement_type == MovementType.RECEIPT


def allocate_fefo(lots: list[StockLot], unlotted: float, requested: float,
                  today: date) -> list[tuple[Optional[StockLot], float]]:
    """
    Distribui uma saída pelos lotes válidos, do vencimento mais próximo ao mais distante
    (FEFO), e usa o estoque sem lote (legado) por último. Lotes vencidos nunca são usados.
    """
    if requested <= 0:
        raise BusinessRuleViolation("A quantidade deve ser positiva.")
    usable = sorted((lot for lot in lots if lot.quantity > 0 and not lot.is_expired(today)),
                    key=lambda lot: (lot.expiration_date, lot.received_at))
    available = sum(lot.quantity for lot in usable) + max(unlotted, 0)
    if requested > available:
        raise ConflictError(f"Estoque válido insuficiente: solicitado {requested:g}, disponível {available:g}.")
    plan, remaining = [], requested
    for lot in usable:
        portion = min(lot.quantity, remaining)
        plan.append((lot, portion))
        remaining -= portion
        if remaining == 0:
            return plan
    plan.append((None, remaining))
    return plan


# -------------------------------------------------------------------- prescrição

class AdministrationRoute(Enum):
    ORAL = "ORAL"
    SUBLINGUAL = "SUBLINGUAL"
    TOPICAL = "TOPICA"
    INHALATION = "INALATORIA"
    INTRAVENOUS = "INTRAVENOSA"
    INTRAMUSCULAR = "INTRAMUSCULAR"
    SUBCUTANEOUS = "SUBCUTANEA"


class PrescriptionStatus(Enum):
    ACTIVE = "ATIVA"
    PARTIALLY_DISPENSED = "PARCIALMENTE_DISPENSADA"
    DISPENSED = "DISPENSADA"
    CANCELLED = "CANCELADA"


class ItemStatus(Enum):
    IN_USE = "EM_USO"
    SUSPENDED = "SUSPENSO"
    COMPLETED = "CONCLUIDO"


@dataclass
class PrescriptionItem:
    medication_id: uuid.UUID
    dose: str                 # ex.: "1 comprimido"
    frequency: str            # ex.: "de 8 em 8 horas"
    duration_days: int
    quantity: float
    route: AdministrationRoute = AdministrationRoute.ORAL
    instructions: Optional[str] = None
    dispensed_quantity: float = 0
    status: ItemStatus = ItemStatus.IN_USE
    status_reason: Optional[str] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        if not self.dose.strip() or not self.frequency.strip():
            raise BusinessRuleViolation("Dose e frequência são obrigatórias.")
        if not 1 <= self.duration_days <= 365:
            raise BusinessRuleViolation("A duração do tratamento deve estar entre 1 e 365 dias.")
        if not 0 < self.quantity <= MAX_ITEM_QUANTITY:
            raise BusinessRuleViolation(f"A quantidade prescrita deve estar entre 1 e {MAX_ITEM_QUANTITY}.")

    @property
    def remaining(self) -> float:
        return max(self.quantity - self.dispensed_quantity, 0)

    def register_dispensed(self, amount: float) -> None:
        if self.status != ItemStatus.IN_USE:
            raise BusinessRuleViolation("Somente itens em uso podem ser dispensados.")
        if amount <= 0 or amount > self.remaining:
            raise BusinessRuleViolation(
                f"Quantidade acima do saldo da prescrição (restam {self.remaining:g}).")
        self.dispensed_quantity += amount

    def suspend(self, reason: str) -> None:
        if self.status != ItemStatus.IN_USE:
            raise InvalidTransitionError("Item da prescrição", self.status.value, ItemStatus.SUSPENDED.value)
        if not reason or len(reason.strip()) < 3:
            raise BusinessRuleViolation("Informe o motivo da suspensão (mínimo de 3 caracteres).")
        self.status, self.status_reason = ItemStatus.SUSPENDED, reason.strip()

    def resume(self) -> None:
        if self.status != ItemStatus.SUSPENDED:
            raise InvalidTransitionError("Item da prescrição", self.status.value, ItemStatus.IN_USE.value)
        self.status, self.status_reason = ItemStatus.IN_USE, None

    def complete(self) -> None:
        if self.status != ItemStatus.IN_USE:
            raise InvalidTransitionError("Item da prescrição", self.status.value, ItemStatus.COMPLETED.value)
        self.status = ItemStatus.COMPLETED


@dataclass
class Prescription:
    patient_id: uuid.UUID
    prescriber_id: uuid.UUID
    issued_at: datetime
    items: list[PrescriptionItem]
    appointment_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    special_control: bool = False
    allergy_override_reason: Optional[str] = None
    status: PrescriptionStatus = PrescriptionStatus.ACTIVE
    cancellation_reason: Optional[str] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        if not self.items:
            raise BusinessRuleViolation("A prescrição precisa de pelo menos um item.")
        medications = [item.medication_id for item in self.items]
        if len(medications) != len(set(medications)):
            raise BusinessRuleViolation("O mesmo medicamento não pode aparecer duas vezes na prescrição.")

    @property
    def valid_until(self) -> datetime:
        return self.issued_at + timedelta(days=PRESCRIPTION_VALIDITY_DAYS)

    def is_expired(self, now: datetime) -> bool:
        return now > self.valid_until

    def item(self, item_id: uuid.UUID) -> PrescriptionItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise BusinessRuleViolation("O item informado não pertence a esta prescrição.")

    def ensure_dispensable(self, now: datetime) -> None:
        if self.status not in (PrescriptionStatus.ACTIVE, PrescriptionStatus.PARTIALLY_DISPENSED):
            raise InvalidTransitionError("Prescrição", self.status.value, PrescriptionStatus.DISPENSED.value)
        if self.is_expired(now):
            raise BusinessRuleViolation(
                f"Prescrição vencida em {self.valid_until:%d/%m/%Y}; é necessária uma nova prescrição.")

    def refresh_status(self) -> None:
        """Recalcula o status a partir dos itens após uma dispensação ou mudança de item."""
        if self.status == PrescriptionStatus.CANCELLED:
            return
        pending = [i for i in self.items if i.status == ItemStatus.IN_USE and i.remaining > 0]
        dispensed_any = any(i.dispensed_quantity > 0 for i in self.items)
        if not pending and dispensed_any:
            self.status = PrescriptionStatus.DISPENSED
        elif dispensed_any:
            self.status = PrescriptionStatus.PARTIALLY_DISPENSED
        else:
            self.status = PrescriptionStatus.ACTIVE

    def cancel(self, reason: str) -> None:
        if self.status in (PrescriptionStatus.DISPENSED, PrescriptionStatus.CANCELLED):
            raise InvalidTransitionError("Prescrição", self.status.value, PrescriptionStatus.CANCELLED.value)
        if not reason or len(reason.strip()) < 3:
            raise BusinessRuleViolation("Informe o motivo do cancelamento (mínimo de 3 caracteres).")
        self.status, self.cancellation_reason = PrescriptionStatus.CANCELLED, reason.strip()


# ------------------------------------------------------------------- dispensação

@dataclass
class DispensationLine:
    prescription_item_id: uuid.UUID
    medication_id: uuid.UUID
    quantity: float
    lot_id: Optional[uuid.UUID] = None  # None = estoque sem lote (legado)
    lot_number: Optional[str] = None


@dataclass
class Dispensation:
    prescription_id: uuid.UUID
    patient_id: uuid.UUID
    pharmacist_id: uuid.UUID
    location: str
    dispensed_at: datetime
    lines: list[DispensationLine] = field(default_factory=list)
    notes: Optional[str] = None
    id: Optional[uuid.UUID] = None
