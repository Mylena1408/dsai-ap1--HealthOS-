from datetime import datetime
from typing import Callable, Optional
import uuid

from app.application.dtos.common import Page
from app.application.dtos.pharmacy_dto import (
    CategoryCreateDTO, CategoryDTO, LotDTO, LotReceiveDTO, MedicationDetailsDTO, MovementDTO, StockOverviewDTO,
)
from app.application.interfaces.medication_repository import MedicationRepository
from app.application.interfaces.pharmacy_repository import LotFilters, MovementFilters, PharmacyRepository
from app.application.services.stock_service import StockService
from app.domain.entities.pharmacy import CatalogStatus, MedicationCategory, MedicationDetails, StockLot
from app.domain.exceptions.common import BusinessRuleViolation, ConflictError, EntityNotFoundError


class PharmacyStockUseCase:
    """Catálogo complementar, lotes, validade e movimentações de estoque."""

    def __init__(self, repo: PharmacyRepository, stock: StockService, medication_repo: MedicationRepository,
                 clock: Callable[[], datetime] = datetime.now):
        self.repo = repo
        self.stock = stock
        self.medication_repo = medication_repo
        self.clock = clock

    # --------------------------------------------------------------- catálogo

    async def categories(self) -> list[CategoryDTO]:
        return [CategoryDTO(id=c.id, name=c.name, description=c.description) for c in await self.repo.list_categories()]

    async def create_category(self, dto: CategoryCreateDTO) -> CategoryDTO:
        if await self.repo.get_category_by_name(dto.name.strip()):
            raise ConflictError(f"Já existe a categoria '{dto.name}'.")
        category = await self.repo.save_category(MedicationCategory(name=dto.name.strip(), description=dto.description))
        return CategoryDTO(id=category.id, name=category.name, description=category.description)

    async def set_details(self, medication_id: uuid.UUID, dto: MedicationDetailsDTO) -> MedicationDetailsDTO:
        await self._medication(medication_id)
        if dto.category_id and not await self.repo.get_category(dto.category_id):
            raise EntityNotFoundError("Categoria", dto.category_id)
        details = await self.repo.save_details(MedicationDetails(medication_id=medication_id, **dto.model_dump()))
        return MedicationDetailsDTO(category_id=details.category_id, catalog_status=details.catalog_status,
                                    requires_prescription=details.requires_prescription)

    async def overview(self, query: Optional[str] = None, category_id: Optional[uuid.UUID] = None,
                       low_stock_only: bool = False) -> list[StockOverviewDTO]:
        categories = {c.id: c.name for c in await self.repo.list_categories()}
        rows = await self.repo.stock_overview(query, category_id, low_stock_only)
        return [StockOverviewDTO(
            medication_id=r.medication.id, name=r.medication.name, generic_name=r.medication.generic_name,
            dosage=r.medication.dosage, unit=r.medication.unit.value, is_controlled=r.medication.is_controlled_substance,
            category_id=r.details.category_id if r.details else None,
            category_name=categories.get(r.details.category_id) if r.details else None,
            catalog_status=r.details.catalog_status if r.details else CatalogStatus.ACTIVE,
            total_quantity=r.total, lotted_quantity=min(r.lotted, r.total), unlotted_quantity=max(r.total - r.lotted, 0),
            below_minimum_locations=r.below_minimum_locations, nearest_expiration=r.nearest_expiration,
        ) for r in rows]

    # ------------------------------------------------------------------ lotes

    async def receive_lot(self, dto: LotReceiveDTO) -> LotDTO:
        await self._medication(dto.medication_id)
        details = await self.repo.get_details(dto.medication_id)
        if details and details.catalog_status == CatalogStatus.DISCONTINUED:
            raise BusinessRuleViolation("Medicamento descontinuado não pode receber novos lotes.")
        lot = await self.stock.receive(dto.medication_id, dto.location.strip().upper(), dto.lot_number,
                                       dto.expiration_date, dto.quantity, self.clock())
        return (await self._lot_dtos([lot]))[0]

    async def discard_lot(self, lot_id: uuid.UUID, reason: Optional[str]) -> LotDTO:
        lot = await self.repo.get_lot(lot_id)
        if not lot:
            raise EntityNotFoundError("Lote", lot_id)
        return (await self._lot_dtos([await self.stock.discard(lot, reason, self.clock())]))[0]

    async def search_lots(self, filters: LotFilters) -> Page[LotDTO]:
        if filters.location:
            filters.location = filters.location.strip().upper()
        lots, total = await self.repo.search_lots(filters)
        return Page(items=await self._lot_dtos(lots), total=total, limit=filters.limit, offset=filters.offset)

    async def search_movements(self, filters: MovementFilters) -> Page[MovementDTO]:
        movements, total = await self.repo.search_movements(filters)
        names = await self.repo.medications_by_ids({m.medication_id for m in movements})
        return Page(items=[MovementDTO(
            id=m.id, medication_id=m.medication_id, medication_name=names[m.medication_id].name if m.medication_id in names else None,
            location=m.location, movement_type=m.movement_type, quantity=m.quantity, balance_after=m.balance_after,
            lot_id=m.lot_id, reference_id=m.reference_id, reason=m.reason, occurred_at=m.occurred_at,
        ) for m in movements], total=total, limit=filters.limit, offset=filters.offset)

    # ------------------------------------------------------------------ apoio

    async def _medication(self, medication_id: uuid.UUID):
        medication = await self.medication_repo.get_by_id(medication_id)
        if not medication:
            raise EntityNotFoundError("Medicamento", medication_id)
        return medication

    async def _lot_dtos(self, lots: list[StockLot]) -> list[LotDTO]:
        today = self.clock().date()
        names = await self.repo.medications_by_ids({lot.medication_id for lot in lots})
        return [LotDTO(
            id=lot.id, medication_id=lot.medication_id,
            medication_name=names[lot.medication_id].name if lot.medication_id in names else None,
            location=lot.location, lot_number=lot.lot_number, expiration_date=lot.expiration_date,
            days_to_expire=(lot.expiration_date - today).days, is_expired=lot.is_expired(today),
            quantity=lot.quantity, received_at=lot.received_at,
        ) for lot in lots]
