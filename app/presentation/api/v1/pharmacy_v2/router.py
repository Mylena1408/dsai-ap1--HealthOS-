"""Farmácia expandida: catálogo complementar, lotes, prescrições e dispensações.

As rotas legadas em /api/v1/pharmacy/... continuam inalteradas (ADR-014).
"""
from datetime import date, datetime, time, timedelta
from typing import Literal, Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.common import Page
from app.application.dtos.pharmacy_dto import (
    CategoryCreateDTO, CategoryDTO, DiscardDTO, DispensationCreateDTO, DispensationDTO, LotDTO, LotReceiveDTO,
    MedicationDetailsDTO, MovementDTO, PatientMedicationDTO, PrescriptionCreateDTO, PrescriptionDTO, ReasonDTO,
    StockOverviewDTO,
)
from app.application.interfaces.pharmacy_repository import LotFilters, MovementFilters, PrescriptionFilters
from app.application.services.stock_service import StockService
from app.application.use_cases.pharmacy_stock_use_case import PharmacyStockUseCase
from app.application.use_cases.prescription_use_case import PrescriptionUseCase
from app.domain.entities.pharmacy import ItemStatus, MovementType, PrescriptionStatus
from app.infrastructure.persistence.database import get_db
from app.presentation.api.dependencies import get_events
from app.infrastructure.persistence.repositories.sqlalchemy_appointment_repository import SQLAlchemyAppointmentRepository
from app.infrastructure.persistence.repositories.sqlalchemy_medical_record_repository import (
    SQLAlchemyMedicalRecordRepository, SQLAlchemyPatientDirectoryRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_medication_repository import (
    SQLAlchemyInventoryRepository, SQLAlchemyMedicationRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_pharmacy_repository import SQLAlchemyPharmacyRepository
from app.infrastructure.persistence.repositories.sqlalchemy_professional_repository import (
    SQLAlchemyProfessionalRepository,
)

router = APIRouter()


async def get_stock(session: AsyncSession = Depends(get_db), events=Depends(get_events)) -> PharmacyStockUseCase:
    repo = SQLAlchemyPharmacyRepository(session)
    return PharmacyStockUseCase(repo, StockService(repo, SQLAlchemyInventoryRepository(session)),
                                SQLAlchemyMedicationRepository(session), events=events)


async def get_prescriptions(session: AsyncSession = Depends(get_db), events=Depends(get_events)) -> PrescriptionUseCase:
    repo = SQLAlchemyPharmacyRepository(session)
    return PrescriptionUseCase(
        repo, SQLAlchemyPatientDirectoryRepository(session), SQLAlchemyProfessionalRepository(session),
        SQLAlchemyAppointmentRepository(session), SQLAlchemyMedicalRecordRepository(session),
        StockService(repo, SQLAlchemyInventoryRepository(session)), events=events)


Stock = Depends(get_stock)
Prescriptions = Depends(get_prescriptions)
TAG_STOCK, TAG_RX = "Farmácia — Estoque e Lotes", "Farmácia — Prescrições e Dispensações"


# ----------------------------------------------------------------- catálogo e estoque

@router.get("/medication-categories", response_model=list[CategoryDTO], tags=[TAG_STOCK])
async def list_categories(use_case: PharmacyStockUseCase = Stock):
    return await use_case.categories()


@router.post("/medication-categories", response_model=CategoryDTO, status_code=status.HTTP_201_CREATED, tags=[TAG_STOCK])
async def create_category(request: CategoryCreateDTO, use_case: PharmacyStockUseCase = Stock):
    return await use_case.create_category(request)


@router.get("/medications/stock", response_model=list[StockOverviewDTO], tags=[TAG_STOCK],
            summary="Posição de estoque consolidada por medicamento")
async def stock_overview(q: Optional[str] = Query(None, max_length=100), category_id: Optional[uuid.UUID] = None,
                         low_stock_only: bool = False, use_case: PharmacyStockUseCase = Stock):
    return await use_case.overview(q, category_id, low_stock_only)


@router.put("/medications/{medication_id}/details", response_model=MedicationDetailsDTO, tags=[TAG_STOCK])
async def set_medication_details(medication_id: uuid.UUID, request: MedicationDetailsDTO,
                                 use_case: PharmacyStockUseCase = Stock):
    return await use_case.set_details(medication_id, request)


@router.get("/stock/lots", response_model=Page[LotDTO], tags=[TAG_STOCK])
async def search_lots(medication_id: Optional[uuid.UUID] = None, location: Optional[str] = None,
                      expiring_within_days: Optional[int] = Query(None, ge=0, le=3650,
                                                                  description="Inclui lotes já vencidos"),
                      include_empty: bool = False, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                      use_case: PharmacyStockUseCase = Stock):
    expiring_before = date.today() + timedelta(days=expiring_within_days) if expiring_within_days is not None else None
    return await use_case.search_lots(LotFilters(medication_id=medication_id, location=location,
                                                 expiring_before=expiring_before, include_empty=include_empty,
                                                 limit=limit, offset=offset))


@router.post("/stock/lots", response_model=LotDTO, status_code=status.HTTP_201_CREATED, tags=[TAG_STOCK],
             summary="Recebe um lote (entrada de estoque)")
async def receive_lot(request: LotReceiveDTO, use_case: PharmacyStockUseCase = Stock):
    return await use_case.receive_lot(request)


@router.post("/stock/lots/{lot_id}/discard", response_model=LotDTO, tags=[TAG_STOCK])
async def discard_lot(lot_id: uuid.UUID, request: DiscardDTO, use_case: PharmacyStockUseCase = Stock):
    return await use_case.discard_lot(lot_id, request.reason)


@router.get("/stock/movements", response_model=Page[MovementDTO], tags=[TAG_STOCK])
async def search_movements(medication_id: Optional[uuid.UUID] = None, location: Optional[str] = None,
                           movement_type: Optional[MovementType] = None, reference_id: Optional[uuid.UUID] = None,
                           date_from: Optional[date] = None, date_to: Optional[date] = None,
                           limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                           use_case: PharmacyStockUseCase = Stock):
    return await use_case.search_movements(MovementFilters(
        medication_id=medication_id, location=location.strip().upper() if location else None,
        movement_type=movement_type, reference_id=reference_id,
        date_from=datetime.combine(date_from, time.min) if date_from else None,
        date_to=datetime.combine(date_to, time.max) if date_to else None, limit=limit, offset=offset))


# ------------------------------------------------------------ prescrições e dispensação

@router.post("/prescriptions", response_model=PrescriptionDTO, status_code=status.HTTP_201_CREATED, tags=[TAG_RX])
async def prescribe(request: PrescriptionCreateDTO, use_case: PrescriptionUseCase = Prescriptions):
    return await use_case.prescribe(request)


@router.get("/prescriptions", response_model=Page[PrescriptionDTO], tags=[TAG_RX])
async def search_prescriptions(patient_id: Optional[uuid.UUID] = None, prescriber_id: Optional[uuid.UUID] = None,
                               status_: Optional[list[PrescriptionStatus]] = Query(None, alias="status"),
                               limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                               use_case: PrescriptionUseCase = Prescriptions):
    return await use_case.search(PrescriptionFilters(patient_id=patient_id, prescriber_id=prescriber_id,
                                                     statuses=status_ or [], limit=limit, offset=offset))


@router.get("/prescriptions/{prescription_id}", response_model=PrescriptionDTO, tags=[TAG_RX])
async def get_prescription(prescription_id: uuid.UUID, use_case: PrescriptionUseCase = Prescriptions):
    return await use_case.get(prescription_id)


@router.post("/prescriptions/{prescription_id}/cancel", response_model=PrescriptionDTO, tags=[TAG_RX])
async def cancel_prescription(prescription_id: uuid.UUID, request: ReasonDTO,
                              use_case: PrescriptionUseCase = Prescriptions):
    return await use_case.cancel(prescription_id, request.reason)


@router.post("/prescriptions/{prescription_id}/items/{item_id}/{action}", response_model=PrescriptionDTO, tags=[TAG_RX],
             summary="Suspende, retoma ou conclui um item (suspend exige motivo)")
async def change_prescription_item(prescription_id: uuid.UUID, item_id: uuid.UUID,
                                   action: Literal["suspend", "resume", "complete"],
                                   request: Optional[ReasonDTO] = None, use_case: PrescriptionUseCase = Prescriptions):
    return await use_case.change_item(prescription_id, item_id, action, request.reason if request else None)


@router.post("/dispensations", response_model=DispensationDTO, status_code=status.HTTP_201_CREATED, tags=[TAG_RX],
             summary="Dispensa itens de uma prescrição com baixa FEFO no estoque")
async def dispense(request: DispensationCreateDTO, use_case: PrescriptionUseCase = Prescriptions):
    return await use_case.dispense(request)


@router.get("/dispensations", response_model=Page[DispensationDTO], tags=[TAG_RX])
async def list_dispensations(prescription_id: Optional[uuid.UUID] = None, patient_id: Optional[uuid.UUID] = None,
                             limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                             use_case: PrescriptionUseCase = Prescriptions):
    return await use_case.dispensations(prescription_id, patient_id, limit, offset)


@router.get("/patients/{patient_id}/medications", response_model=list[PatientMedicationDTO], tags=[TAG_RX],
            summary="Medicamentos do paciente (em uso, suspensos e concluídos)")
async def patient_medications(patient_id: uuid.UUID, status_: Optional[ItemStatus] = Query(None, alias="status"),
                              use_case: PrescriptionUseCase = Prescriptions):
    return await use_case.patient_medications(patient_id, status_)
