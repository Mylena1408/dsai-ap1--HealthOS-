from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from pydantic import BaseModel, Field
from datetime import datetime

from app.infrastructure.persistence.repositories.sqlalchemy_medication_repository import SQLAlchemyMedicationRepository
from app.application.use_cases.pharmacy_use_case import PharmacyUseCase
from app.infrastructure.security.permission_checker import PermissionChecker
from app.domain.exceptions.base import DomainException
from app.infrastructure.persistence.database import get_db

# DTOs para a API de Farmácia
class MedicationCreateDTO(BaseModel):
    name: str
    generic_name: str
    dosage: str
    unit: str
    is_controlled: bool = False
    manufacturer: Optional[str] = None
    description: Optional[str] = None

class StockUpdateDTO(BaseModel):
    quantity: float
    expiration_date: Optional[datetime] = None

class DispenseDTO(BaseModel):
    quantity: float

router = APIRouter(prefix="/pharmacy", tags=["Farmácia e Suprimentos"])

async def get_pharmacy_use_case(session: AsyncSession = Depends(get_db)):
    # Injeção de dependências manual para o exemplo
    from app.infrastructure.persistence.repositories.sqlalchemy_medication_repository import SQLAlchemyMedicationRepository, SQLAlchemyInventoryRepository
    med_repo = SQLAlchemyMedicationRepository(session)
    inv_repo = SQLAlchemyInventoryRepository(session)
    return PharmacyUseCase(med_repo, inv_repo)
    # Injeção de dependências manual para o exemplo
    from app.infrastructure.persistence.repositories.sqlalchemy_medication_repository import SQLAlchemyMedicationRepository, SQLAlchemyInventoryRepository
    med_repo = SQLAlchemyMedicationRepository(session)
    inv_repo = SQLAlchemyInventoryRepository(session)
    return PharmacyUseCase(med_repo, inv_repo)

@router.post("/medications", status_code=status.HTTP_201_CREATED,
              dependencies=[Depends(PermissionChecker(["pharmacy:write"]))])
async def create_medication(request: MedicationCreateDTO, use_case: PharmacyUseCase = Depends(get_pharmacy_use_case)):
    try:
        return await use_case.register_medication(
            request.name, request.generic_name, request.dosage, request.unit,
            request.is_controlled, request.manufacturer, request.description
        )
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.post("/inventory/{medication_id}/{location_id}", status_code=status.HTTP_201_CREATED,
              dependencies=[Depends(PermissionChecker(["pharmacy:write"]))])
async def add_stock(medication_id: uuid.UUID, location_id: str, request: StockUpdateDTO,
                   use_case: PharmacyUseCase = Depends(get_pharmacy_use_case)):
    try:
        return await use_case.add_inventory_stock(medication_id, location_id, request.quantity, request.expiration_date)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.post("/dispense/{medication_id}/{location_id}",
              dependencies=[Depends(PermissionChecker(["pharmacy:dispense"]))])
async def dispense_medication(medication_id: uuid.UUID, location_id: str, request: DispenseDTO,
                             use_case: PharmacyUseCase = Depends(get_pharmacy_use_case)):
    try:
        return await use_case.dispense_medication(medication_id, location_id, request.quantity)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.get("/critical-stock", dependencies=[Depends(PermissionChecker(["pharmacy:read"]))])
async def get_critical_stock(use_case: PharmacyUseCase = Depends(get_pharmacy_use_case)):
    return await use_case.get_critical_stock_report()
