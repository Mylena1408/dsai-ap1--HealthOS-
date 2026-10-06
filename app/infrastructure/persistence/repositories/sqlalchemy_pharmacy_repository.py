import uuid

from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.pharmacy_repository import (
    LotFilters, MovementFilters, PharmacyRepository, PrescriptionFilters, StockRow,
)
from app.domain.entities.pharmacy import (
    AdministrationRoute, CatalogStatus, Dispensation, DispensationLine, InventoryMovement, ItemStatus,
    MedicationCategory, MedicationDetails, MovementType, Prescription, PrescriptionItem, PrescriptionStatus, StockLot,
)
from app.infrastructure.persistence.models.medication_model import InventoryItemModel, MedicationModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.models.pharmacy_model import (
    DispensationLineModel, DispensationModel, InventoryMovementModel, MedicationCategoryModel, MedicationDetailsModel,
    PrescriptionItemModel, PrescriptionModel, StockLotModel,
)
from app.infrastructure.persistence.repositories.sqlalchemy_medication_repository import SQLAlchemyMedicationRepository

_ITEM_FIELDS = ("medication_id", "dose", "frequency", "duration_days", "quantity", "dispensed_quantity",
                "instructions", "status_reason")


class SQLAlchemyPharmacyRepository(PharmacyRepository):

    def __init__(self, session: AsyncSession):
        self.session = session
        self._medications = SQLAlchemyMedicationRepository(session)

    # --------------------------------------------------------------- catálogo

    async def list_categories(self):
        rows = await self.session.scalars(select(MedicationCategoryModel).order_by(MedicationCategoryModel.name))
        return [MedicationCategory(id=m.id, name=m.name, description=m.description) for m in rows]

    async def get_category(self, category_id):
        m = await self.session.get(MedicationCategoryModel, category_id)
        return MedicationCategory(id=m.id, name=m.name, description=m.description) if m else None

    async def get_category_by_name(self, name):
        m = await self.session.scalar(select(MedicationCategoryModel)
                                      .where(func.lower(MedicationCategoryModel.name) == name.lower()))
        return MedicationCategory(id=m.id, name=m.name, description=m.description) if m else None

    async def save_category(self, category):
        model = await self.session.get(MedicationCategoryModel, category.id) if category.id else None
        if model is None:
            model = MedicationCategoryModel(id=category.id or uuid.uuid4())
            self.session.add(model)
        model.name, model.description = category.name, category.description
        await self.session.flush()
        category.id = model.id
        return category

    async def get_details(self, medication_id):
        m = await self.session.get(MedicationDetailsModel, medication_id)
        return self._details(m) if m else None

    async def save_details(self, details):
        model = await self.session.get(MedicationDetailsModel, details.medication_id)
        if model is None:
            model = MedicationDetailsModel(medication_id=details.medication_id)
            self.session.add(model)
        model.category_id = details.category_id
        model.catalog_status = details.catalog_status.value
        model.requires_prescription = details.requires_prescription
        await self.session.flush()
        return details

    async def medications_by_ids(self, ids):
        if not ids:
            return {}
        rows = await self.session.scalars(select(MedicationModel).where(MedicationModel.id.in_(ids)))
        return {m.id: self._medications._map_to_domain(m) for m in rows}

    async def patient_names(self, ids):
        if not ids:
            return {}
        rows = await self.session.execute(select(PatientModel.id, PatientModel.full_name).where(PatientModel.id.in_(ids)))
        return dict(rows.all())

    async def stock_overview(self, query, category_id, low_stock_only):
        # Três consultas agregadas (totais, lotes, detalhes) em vez de uma por medicamento.
        totals = {row.medication_id: row for row in (await self.session.execute(
            select(InventoryItemModel.medication_id,
                   func.sum(InventoryItemModel.quantity).label("total"),
                   func.sum(case((InventoryItemModel.quantity <= InventoryItemModel.min_threshold, 1), else_=0)).label("low"))
            .group_by(InventoryItemModel.medication_id))).all()}
        lots = {row.medication_id: row for row in (await self.session.execute(
            select(StockLotModel.medication_id, func.sum(StockLotModel.quantity).label("lotted"),
                   func.min(StockLotModel.expiration_date).label("nearest"))
            .where(StockLotModel.quantity > 0).group_by(StockLotModel.medication_id))).all()}
        details = {m.medication_id: self._details(m) for m in await self.session.scalars(select(MedicationDetailsModel))}

        conditions = []
        if query:
            pattern = f"%{query.strip()}%"
            conditions.append(or_(MedicationModel.name.ilike(pattern), MedicationModel.generic_name.ilike(pattern)))
        medications = await self.session.scalars(select(MedicationModel).where(*conditions).order_by(MedicationModel.name))

        rows = []
        for model in medications:
            detail = details.get(model.id)
            if category_id and (not detail or detail.category_id != category_id):
                continue
            total_row, lot_row = totals.get(model.id), lots.get(model.id)
            low = int(total_row.low or 0) if total_row else 0
            if low_stock_only and not low:
                continue
            rows.append(StockRow(
                medication=self._medications._map_to_domain(model), details=detail,
                total=float(total_row.total or 0) if total_row else 0.0,
                lotted=float(lot_row.lotted or 0) if lot_row else 0.0,
                below_minimum_locations=low, nearest_expiration=lot_row.nearest if lot_row else None))
        return rows

    # ------------------------------------------------------- lotes e movimentos

    async def save_lot(self, lot):
        model = await self.session.get(StockLotModel, lot.id) if lot.id else None
        if model is None:
            model = StockLotModel(id=lot.id or uuid.uuid4())
            self.session.add(model)
        for name in ("medication_id", "location", "lot_number", "expiration_date", "quantity", "received_at"):
            setattr(model, name, getattr(lot, name))
        await self.session.flush()
        lot.id = model.id
        return lot

    async def get_lot(self, lot_id):
        m = await self.session.get(StockLotModel, lot_id)
        return self._lot(m) if m else None

    async def find_lot(self, medication_id, location, lot_number):
        m = await self.session.scalar(select(StockLotModel).where(
            StockLotModel.medication_id == medication_id, StockLotModel.location == location,
            StockLotModel.lot_number == lot_number))
        return self._lot(m) if m else None

    async def lots_for(self, medication_id, location):
        rows = await self.session.scalars(select(StockLotModel).where(
            StockLotModel.medication_id == medication_id, StockLotModel.location == location))
        return [self._lot(m) for m in rows]

    async def search_lots(self, filters: LotFilters):
        conditions = []
        if not filters.include_empty:
            conditions.append(StockLotModel.quantity > 0)
        if filters.medication_id:
            conditions.append(StockLotModel.medication_id == filters.medication_id)
        if filters.location:
            conditions.append(StockLotModel.location == filters.location)
        if filters.expiring_before:
            conditions.append(StockLotModel.expiration_date <= filters.expiring_before)
        total = await self.session.scalar(select(func.count()).select_from(StockLotModel).where(*conditions))
        rows = await self.session.scalars(select(StockLotModel).where(*conditions)
                                          .order_by(StockLotModel.expiration_date).limit(filters.limit).offset(filters.offset))
        return [self._lot(m) for m in rows], total

    async def add_movement(self, movement):
        model = InventoryMovementModel(
            id=movement.id or uuid.uuid4(), medication_id=movement.medication_id, location=movement.location,
            movement_type=movement.movement_type.value, quantity=movement.quantity, balance_after=movement.balance_after,
            lot_id=movement.lot_id, reference_id=movement.reference_id, reason=movement.reason,
            occurred_at=movement.occurred_at)
        self.session.add(model)
        await self.session.flush()
        movement.id = model.id
        return movement

    async def search_movements(self, filters: MovementFilters):
        conditions = []
        for column, value in ((InventoryMovementModel.medication_id, filters.medication_id),
                              (InventoryMovementModel.location, filters.location),
                              (InventoryMovementModel.reference_id, filters.reference_id)):
            if value:
                conditions.append(column == value)
        if filters.movement_type:
            conditions.append(InventoryMovementModel.movement_type == filters.movement_type.value)
        if filters.date_from:
            conditions.append(InventoryMovementModel.occurred_at >= filters.date_from)
        if filters.date_to:
            conditions.append(InventoryMovementModel.occurred_at <= filters.date_to)
        total = await self.session.scalar(select(func.count()).select_from(InventoryMovementModel).where(*conditions))
        rows = await self.session.scalars(select(InventoryMovementModel).where(*conditions)
                                          .order_by(desc(InventoryMovementModel.occurred_at)).limit(filters.limit)
                                          .offset(filters.offset))
        return [InventoryMovement(
            id=m.id, medication_id=m.medication_id, location=m.location, movement_type=MovementType(m.movement_type),
            quantity=m.quantity, balance_after=m.balance_after, lot_id=m.lot_id, reference_id=m.reference_id,
            reason=m.reason, occurred_at=m.occurred_at) for m in rows], total

    # ------------------------------------------------- prescrições e dispensação

    async def save_prescription(self, prescription):
        model = await self.session.get(PrescriptionModel, prescription.id) if prescription.id else None
        if model is None:
            model = PrescriptionModel(id=prescription.id or uuid.uuid4(), items=[])
            self.session.add(model)
        for name in ("patient_id", "prescriber_id", "appointment_id", "issued_at", "special_control",
                     "allergy_override_reason", "notes", "cancellation_reason"):
            setattr(model, name, getattr(prescription, name))
        model.status = prescription.status.value
        existing = {i.id: i for i in model.items}
        for position, item in enumerate(prescription.items):
            item.id = item.id or uuid.uuid4()
            row = existing.get(item.id)
            if row is None:
                row = PrescriptionItemModel(id=item.id, position=position)
                model.items.append(row)
            for name in _ITEM_FIELDS:
                setattr(row, name, getattr(item, name))
            row.route, row.status = item.route.value, item.status.value
        await self.session.flush()
        prescription.id = model.id
        return prescription

    async def get_prescription(self, prescription_id):
        m = await self.session.get(PrescriptionModel, prescription_id)
        return self._prescription(m) if m else None

    async def search_prescriptions(self, filters: PrescriptionFilters):
        conditions = []
        if filters.patient_id:
            conditions.append(PrescriptionModel.patient_id == filters.patient_id)
        if filters.prescriber_id:
            conditions.append(PrescriptionModel.prescriber_id == filters.prescriber_id)
        if filters.statuses:
            conditions.append(PrescriptionModel.status.in_([s.value for s in filters.statuses]))
        if filters.date_from:
            conditions.append(PrescriptionModel.issued_at >= filters.date_from)
        total = await self.session.scalar(select(func.count()).select_from(PrescriptionModel).where(*conditions))
        rows = await self.session.scalars(select(PrescriptionModel).where(*conditions)
                                          .order_by(desc(PrescriptionModel.issued_at)).limit(filters.limit)
                                          .offset(filters.offset))
        return [self._prescription(m) for m in rows], total

    async def save_dispensation(self, dispensation):
        model = DispensationModel(
            id=dispensation.id or uuid.uuid4(), prescription_id=dispensation.prescription_id,
            patient_id=dispensation.patient_id, pharmacist_id=dispensation.pharmacist_id,
            location=dispensation.location, dispensed_at=dispensation.dispensed_at, notes=dispensation.notes,
            lines=[DispensationLineModel(prescription_item_id=l.prescription_item_id, medication_id=l.medication_id,
                                         lot_id=l.lot_id, lot_number=l.lot_number, quantity=l.quantity)
                   for l in dispensation.lines])
        self.session.add(model)
        await self.session.flush()
        dispensation.id = model.id
        return dispensation

    async def list_dispensations(self, prescription_id=None, patient_id=None, limit=50, offset=0):
        conditions = []
        if prescription_id:
            conditions.append(DispensationModel.prescription_id == prescription_id)
        if patient_id:
            conditions.append(DispensationModel.patient_id == patient_id)
        total = await self.session.scalar(select(func.count()).select_from(DispensationModel).where(*conditions))
        rows = await self.session.scalars(select(DispensationModel).where(*conditions)
                                          .order_by(desc(DispensationModel.dispensed_at)).limit(limit).offset(offset))
        return [Dispensation(
            id=m.id, prescription_id=m.prescription_id, patient_id=m.patient_id, pharmacist_id=m.pharmacist_id,
            location=m.location, dispensed_at=m.dispensed_at, notes=m.notes,
            lines=[DispensationLine(prescription_item_id=l.prescription_item_id, medication_id=l.medication_id,
                                    quantity=l.quantity, lot_id=l.lot_id, lot_number=l.lot_number) for l in m.lines],
        ) for m in rows], total

    # -------------------------------------------------------------- mapeamento

    @staticmethod
    def _details(m: MedicationDetailsModel) -> MedicationDetails:
        return MedicationDetails(medication_id=m.medication_id, category_id=m.category_id,
                                 catalog_status=CatalogStatus(m.catalog_status),
                                 requires_prescription=m.requires_prescription)

    @staticmethod
    def _lot(m: StockLotModel) -> StockLot:
        return StockLot(id=m.id, medication_id=m.medication_id, location=m.location, lot_number=m.lot_number,
                        expiration_date=m.expiration_date, quantity=m.quantity, received_at=m.received_at)

    @staticmethod
    def _prescription(m: PrescriptionModel) -> Prescription:
        return Prescription(
            id=m.id, patient_id=m.patient_id, prescriber_id=m.prescriber_id, appointment_id=m.appointment_id,
            issued_at=m.issued_at, status=PrescriptionStatus(m.status), special_control=m.special_control,
            allergy_override_reason=m.allergy_override_reason, notes=m.notes,
            cancellation_reason=m.cancellation_reason,
            items=[PrescriptionItem(id=i.id, route=AdministrationRoute(i.route), status=ItemStatus(i.status),
                                    **{name: getattr(i, name) for name in _ITEM_FIELDS}) for i in m.items],
        )
