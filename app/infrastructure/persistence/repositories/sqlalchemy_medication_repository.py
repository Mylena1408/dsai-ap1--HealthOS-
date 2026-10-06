from typing import List, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.domain.entities.medication import Medication, MedicationUnit, InventoryItem
from app.application.interfaces.medication_repository import MedicationRepository, InventoryRepository
from app.infrastructure.persistence.models.medication_model import MedicationModel, InventoryItemModel

class SQLAlchemyMedicationRepository(MedicationRepository):
    """
    Implementação do MedicationRepository utilizando SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, medication: Medication) -> Medication:
        db_med = MedicationModel(
            id=medication.id or uuid.uuid4(),
            name=medication.name,
            generic_name=medication.generic_name,
            dosage=medication.dosage,
            unit=medication.unit.value,
            is_controlled_substance=medication.is_controlled_substance,
            manufacturer=medication.manufacturer,
            description=medication.description
        )
        self.session.add(db_med)
        await self.session.flush()
        medication.id = db_med.id
        return medication

    async def get_by_id(self, medication_id: uuid.UUID) -> Optional[Medication]:
        result = await self.session.get(MedicationModel, medication_id)
        return self._map_to_domain(result) if result else None

    async def list_all(self) -> List[Medication]:
        result = await self.session.execute(select(MedicationModel))
        return [self._map_to_domain(m) for m in result.scalars().all()]

    async def search_by_name(self, name: str) -> List[Medication]:
        stmt = select(MedicationModel).where(MedicationModel.name.ilike(f"%{name}%"))
        result = await self.session.execute(stmt)
        return [self._map_to_domain(m) for m in result.scalars().all()]

    def _map_to_domain(self, db_model: MedicationModel) -> Medication:
        return Medication(
            id=db_model.id,
            name=db_model.name,
            generic_name=db_model.generic_name,
            dosage=db_model.dosage,
            unit=MedicationUnit(db_model.unit),
            is_controlled_substance=db_model.is_controlled_substance,
            manufacturer=db_model.manufacturer,
            description=db_model.description,
            created_at=db_model.created_at
        )

class SQLAlchemyInventoryRepository(InventoryRepository):
    """
    Implementação do InventoryRepository utilizando SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, item: InventoryItem) -> InventoryItem:
        # Itens já persistidos são atualizados; adicionar um novo modelo com o
        # mesmo id causaria violação de chave primária.
        db_item = await self.session.get(InventoryItemModel, item.id) if item.id else None
        if db_item is None:
            db_item = InventoryItemModel(id=item.id or uuid.uuid4())
            self.session.add(db_item)
        db_item.medication_id = item.medication_id
        db_item.location_id = item.location_id
        db_item.quantity = item.quantity
        db_item.min_threshold = item.min_threshold
        db_item.max_threshold = item.max_threshold
        db_item.expiration_date = item.expiration_date
        await self.session.flush()
        item.id = db_item.id
        return item

    async def get_by_medication_and_location(self, medication_id: uuid.UUID, location_id: uuid.UUID) -> Optional[InventoryItem]:
        stmt = select(InventoryItemModel).where(
            and_(
                InventoryItemModel.medication_id == medication_id,
                InventoryItemModel.location_id == location_id
            )
        )
        result = await self.session.execute(stmt)
        db_item = result.scalar_one_or_none()
        return self._map_to_domain(db_item) if db_item else None

    async def update_quantity(self, item_id: uuid.UUID, new_quantity: float) -> InventoryItem:
        db_item = await self.session.get(InventoryItemModel, item_id)
        if not db_item:
            raise ValueError("Item de inventário não encontrado.")

        db_item.quantity = new_quantity
        await self.session.flush()
        return self._map_to_domain(db_item)

    async def get_low_stock_items(self) -> List[InventoryItem]:
        # Busca itens onde a quantidade é menor ou igual ao limiar mínimo
        stmt = select(InventoryItemModel).where(InventoryItemModel.quantity <= InventoryItemModel.min_threshold)
        result = await self.session.execute(stmt)
        return [self._map_to_domain(i) for i in result.scalars().all()]

    def _map_to_domain(self, db_model: InventoryItemModel) -> InventoryItem:
        return InventoryItem(
            id=db_model.id,
            medication_id=db_model.medication_id,
            location_id=db_model.location_id,
            quantity=db_model.quantity,
            min_threshold=db_model.min_threshold,
            max_threshold=db_model.max_threshold,
            expiration_date=db_model.expiration_date,
            last_updated=db_model.last_updated
        )
