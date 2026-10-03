from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime

from app.infrastructure.persistence.repositories.sqlalchemy_billing_repository import SQLAlchemyBillingRepository
from app.application.use_cases.billing_use_case import BillingUseCase
from app.infrastructure.security.permission_checker import PermissionChecker
from app.domain.exceptions.base import DomainException
from app.infrastructure.persistence.database import get_db

class InvoiceCreateDTO(BaseModel):
    patient_id: uuid.UUID
    invoice_number: str
    insurance_provider: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_coverage: Decimal = Decimal("0.00")

class ChargeItemDTO(BaseModel):
    description: str
    billing_type: str # Corresponde ao BillingType Enum
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal = Decimal("0.00")

router = APIRouter(prefix="/billing", tags=["Faturamento e Convênios"])

async def get_billing_use_case(session: AsyncSession = Depends(get_db)):
    repo = SQLAlchemyBillingRepository(session)
    return BillingUseCase(repo)

@router.post("/invoices", status_code=status.HTTP_201_CREATED,
              dependencies=[Depends(PermissionChecker(["billing:write"]))])
async def create_invoice(request: InvoiceCreateDTO, use_case: BillingUseCase = Depends(get_billing_use_case)):
    try:
        return await use_case.create_invoice(
            request.patient_id, request.invoice_number,
            request.insurance_provider, request.insurance_policy_number, request.insurance_coverage
        )
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.post("/invoices/{invoice_id}/charges",
              dependencies=[Depends(PermissionChecker(["billing:write"]))])
async def add_charge(invoice_id: uuid.UUID, request: ChargeItemDTO, use_case: BillingUseCase = Depends(get_billing_use_case)):
    try:
        from app.domain.entities.billing import BillingType
        return await use_case.add_charge_to_invoice(
            invoice_id, request.description, BillingType(request.billing_type),
            request.quantity, request.unit_price, request.discount
        )
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.post("/invoices/{invoice_id}/finalize",
              dependencies=[Depends(PermissionChecker(["billing:write"]))])
async def finalize_invoice(invoice_id: uuid.UUID, use_case: BillingUseCase = Depends(get_billing_use_case)):
    try:
        return await use_case.finalize_invoice(invoice_id)
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

@router.get("/patients/{patient_id}/summary")
async def get_financial_summary(patient_id: uuid.UUID, use_case: BillingUseCase = Depends(get_billing_use_case)):
    return await use_case.get_patient_financial_summary(patient_id)
