"""Financeiro ampliado: faturas, pagamentos parciais, faturamento de atendimentos e indicadores."""
from datetime import date, datetime, timedelta
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.common import Page
from app.application.dtos.finance_dto import (
    FinanceSummaryDTO, InvoiceCancelDTO, InvoiceDetailDTO, InvoiceFromServicesDTO, InvoiceListItemDTO,
    PaymentCreateDTO, ServicePriceDTO, UnbilledServiceDTO,
)
from app.application.interfaces.finance_queries import InvoiceFilter
from app.application.use_cases.finance_use_case import FinanceUseCase
from app.domain.entities.billing import BillingStatus
from app.domain.exceptions.common import BusinessRuleViolation
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories.sqlalchemy_billing_repository import SQLAlchemyBillingRepository
from app.infrastructure.persistence.repositories.sqlalchemy_finance_queries import SQLAlchemyFinanceQueries
from app.presentation.api.dependencies import get_events

router = APIRouter(prefix="/billing", tags=["Financeiro"])


async def get_finance(session: AsyncSession = Depends(get_db), events=Depends(get_events)) -> FinanceUseCase:
    return FinanceUseCase(SQLAlchemyBillingRepository(session), SQLAlchemyFinanceQueries(session), events)


Finance = Depends(get_finance)


@router.get("/invoices", response_model=Page[InvoiceListItemDTO], summary="Faturas com filtros (ATRASADO = vencida e não quitada)")
async def list_invoices(status_: Optional[BillingStatus] = Query(None, alias="status"),
                        patient_id: Optional[uuid.UUID] = None,
                        start: Optional[date] = Query(None, description="Emitidas a partir de (inclusive)"),
                        end: Optional[date] = Query(None, description="Emitidas até (inclusive)"),
                        number: Optional[str] = Query(None, max_length=50),
                        limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                        finance: FinanceUseCase = Finance):
    if start and end and end < start:
        raise BusinessRuleViolation("A data final deve ser igual ou posterior à inicial.")
    filters = InvoiceFilter(status=status_, patient_id=patient_id, number=number,
                            issued_from=_day_start(start), issued_until=_day_start(end + timedelta(days=1)) if end else None)
    return await finance.page(filters, limit, offset)


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetailDTO)
async def invoice_detail(invoice_id: uuid.UUID, finance: FinanceUseCase = Finance):
    return await finance.detail(invoice_id)


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceDetailDTO, summary="Emite uma fatura em rascunho")
async def issue_invoice(invoice_id: uuid.UUID, finance: FinanceUseCase = Finance):
    return await finance.issue(invoice_id)


@router.post("/invoices/{invoice_id}/payments", response_model=InvoiceDetailDTO, status_code=status.HTTP_201_CREATED,
             summary="Registra um pagamento (parcial ou total)")
async def register_payment(invoice_id: uuid.UUID, request: PaymentCreateDTO, finance: FinanceUseCase = Finance):
    return await finance.register_payment(invoice_id, request.amount, request.method, request.note)


@router.post("/invoices/{invoice_id}/cancel", response_model=InvoiceDetailDTO)
async def cancel_invoice(invoice_id: uuid.UUID, request: InvoiceCancelDTO, finance: FinanceUseCase = Finance):
    return await finance.cancel(invoice_id, request.reason)


@router.get("/patients/{patient_id}/unbilled", response_model=list[UnbilledServiceDTO],
            summary="Consultas finalizadas e exames liberados ainda não faturados")
async def unbilled_services(patient_id: uuid.UUID, finance: FinanceUseCase = Finance):
    return await finance.unbilled(patient_id)


@router.post("/patients/{patient_id}/invoices", response_model=InvoiceDetailDTO, status_code=status.HTTP_201_CREATED,
             summary="Cria uma fatura a partir de atendimentos, com preços da tabela")
async def invoice_services(patient_id: uuid.UUID, request: InvoiceFromServicesDTO, finance: FinanceUseCase = Finance):
    return await finance.invoice_services(patient_id, request)


@router.get("/prices", response_model=list[ServicePriceDTO], summary="Tabela de preços fictícia")
async def price_table(finance: FinanceUseCase = Finance):
    return await finance.prices()


@router.get("/summary", response_model=FinanceSummaryDTO, summary="Indicadores financeiros do período")
async def finance_summary(start: Optional[date] = None, end: Optional[date] = None, finance: FinanceUseCase = Finance):
    return await finance.summary(start, end)


def _day_start(day: Optional[date]) -> Optional[datetime]:
    return datetime.combine(day, datetime.min.time()) if day else None
