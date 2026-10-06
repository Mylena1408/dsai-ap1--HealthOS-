"""Serviço de estoque: lotes, saídas FEFO e coerência com o estoque legado (ADR-014).

O total por medicamento/local continua em 'inventory_items' (legado) e é a fonte da
verdade. Os lotes detalham parte desse total; o restante é "estoque sem lote".
Como os endpoints legados alteram só o total, toda operação nova começa por uma
reconciliação: se a soma dos lotes ultrapassar o total, a diferença é baixada dos
lotes por FEFO e registrada como movimentação de AJUSTE.
"""
from datetime import date, datetime
from typing import Optional
import uuid

from app.application.interfaces.medication_repository import InventoryRepository
from app.application.interfaces.pharmacy_repository import PharmacyRepository
from app.domain.entities.medication import InventoryItem
from app.domain.entities.pharmacy import InventoryMovement, MovementType, StockLot, allocate_fefo
from app.domain.exceptions.common import BusinessRuleViolation, ConflictError

LEGACY_RECONCILIATION_REASON = "Saída registrada pelo endpoint legado (sem lote); baixa nos lotes por FEFO."


class StockService:

    def __init__(self, pharmacy_repo: PharmacyRepository, inventory_repo: InventoryRepository):
        self.repo = pharmacy_repo
        self.inventory = inventory_repo

    async def position(self, medication_id: uuid.UUID, location: str) -> tuple[Optional[InventoryItem], list[StockLot]]:
        return (await self.inventory.get_by_medication_and_location(medication_id, location),
                await self.repo.lots_for(medication_id, location))

    async def reconcile(self, medication_id: uuid.UUID, location: str, now: datetime) -> float:
        """Ajusta os lotes ao total legado. Retorna a quantidade ajustada (0 se já coerente)."""
        aggregate, lots = await self.position(medication_id, location)
        total = aggregate.quantity if aggregate else 0
        excess = sum(lot.quantity for lot in lots) - total
        if excess <= 0:
            return 0
        adjusted = excess
        # Inclui lotes vencidos: a saída legada pode ter usado qualquer unidade física.
        for lot in sorted((lot for lot in lots if lot.quantity > 0), key=lambda lot: lot.expiration_date):
            portion = min(lot.quantity, excess)
            lot.take(portion)
            await self.repo.save_lot(lot)
            await self.repo.add_movement(InventoryMovement(
                medication_id=medication_id, location=location, movement_type=MovementType.ADJUSTMENT,
                quantity=portion, occurred_at=now, balance_after=total, lot_id=lot.id,
                reason=LEGACY_RECONCILIATION_REASON))
            excess -= portion
            if excess <= 0:
                break
        return adjusted

    async def receive(self, medication_id: uuid.UUID, location: str, lot_number: str, expiration_date: date,
                      quantity: float, now: datetime) -> StockLot:
        if quantity <= 0:
            raise BusinessRuleViolation("A quantidade recebida deve ser positiva.")
        if expiration_date <= now.date():
            raise BusinessRuleViolation("Não é possível receber um lote já vencido.")
        await self.reconcile(medication_id, location, now)
        lot = StockLot(medication_id=medication_id, location=location, lot_number=lot_number,
                       expiration_date=expiration_date, quantity=quantity, received_at=now)
        if await self.repo.find_lot(medication_id, location, lot.lot_number):
            raise ConflictError(f"O lote {lot.lot_number} já foi recebido neste local.")

        aggregate = await self.inventory.get_by_medication_and_location(medication_id, location)
        if aggregate is None:
            aggregate = InventoryItem(medication_id=medication_id, location_id=location, quantity=0)
        aggregate.add_stock(quantity)
        # O total legado guarda a validade mais próxima entre os lotes recebidos.
        if aggregate.expiration_date is None or expiration_date < _as_date(aggregate.expiration_date):
            aggregate.expiration_date = datetime.combine(expiration_date, datetime.min.time())
        await self.inventory.save(aggregate)
        lot = await self.repo.save_lot(lot)
        await self.repo.add_movement(InventoryMovement(
            medication_id=medication_id, location=location, movement_type=MovementType.RECEIPT, quantity=quantity,
            occurred_at=now, balance_after=aggregate.quantity, lot_id=lot.id, reason=f"Recebimento do lote {lot.lot_number}"))
        return lot

    async def withdraw(self, medication_id: uuid.UUID, location: str, quantity: float, now: datetime,
                       movement_type: MovementType, reference_id: Optional[uuid.UUID] = None,
                       reason: Optional[str] = None) -> list[tuple[Optional[StockLot], float]]:
        """Saída por FEFO (lotes válidos primeiro, sem lote por último). Retorna o plano executado."""
        await self.reconcile(medication_id, location, now)
        aggregate, lots = await self.position(medication_id, location)
        total = aggregate.quantity if aggregate else 0
        unlotted = total - sum(lot.quantity for lot in lots)
        plan = allocate_fefo(lots, unlotted, quantity, now.date())

        for lot, portion in plan:
            if lot:
                lot.take(portion)
                await self.repo.save_lot(lot)
            aggregate.remove_stock(portion)
            await self.repo.add_movement(InventoryMovement(
                medication_id=medication_id, location=location, movement_type=movement_type, quantity=portion,
                occurred_at=now, balance_after=aggregate.quantity, lot_id=lot.id if lot else None,
                reference_id=reference_id, reason=reason))
        await self.inventory.save(aggregate)
        return plan

    async def discard(self, lot: StockLot, reason: Optional[str], now: datetime) -> StockLot:
        """Descarte do saldo de um lote: livre se vencido; caso contrário exige motivo."""
        await self.reconcile(lot.medication_id, lot.location, now)
        lot = await self.repo.get_lot(lot.id)
        if lot.quantity <= 0:
            raise BusinessRuleViolation("O lote não tem saldo para descartar.")
        expired = lot.is_expired(now.date())
        if not expired and (not reason or len(reason.strip()) < 10):
            raise BusinessRuleViolation("Descartar um lote dentro da validade exige justificativa (mínimo de 10 caracteres).")
        amount = lot.quantity
        lot.take(amount)
        aggregate = await self.inventory.get_by_medication_and_location(lot.medication_id, lot.location)
        aggregate.remove_stock(amount)
        await self.inventory.save(aggregate)
        await self.repo.save_lot(lot)
        await self.repo.add_movement(InventoryMovement(
            medication_id=lot.medication_id, location=lot.location, movement_type=MovementType.DISPOSAL,
            quantity=amount, occurred_at=now, balance_after=aggregate.quantity, lot_id=lot.id,
            reason=reason.strip() if reason else "Lote vencido"))
        return lot


def _as_date(value) -> date:
    return value.date() if isinstance(value, datetime) else value
