"""Faturas fictícias geradas a partir dos atendimentos já semeados.

Passa pelo FinanceUseCase com um relógio controlado, então valem as mesmas regras da
API: preços da tabela, nada é faturado duas vezes, pagamentos não excedem o saldo.
Alguns pacientes ficam com atendimentos ainda não faturados, para a demonstração
do "faturar atendimentos".
"""
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
import random
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dtos.finance_dto import InvoiceFromServicesDTO, ServiceRefDTO
from app.application.use_cases.finance_use_case import FinanceUseCase
from app.domain.entities.billing import CENTS, PaymentMethod
from app.infrastructure.events import build_publisher
from app.infrastructure.persistence.models.billing_model import InvoiceModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.repositories.sqlalchemy_billing_repository import SQLAlchemyBillingRepository
from app.infrastructure.persistence.repositories.sqlalchemy_finance_queries import SQLAlchemyFinanceQueries
from app.infrastructure.seed.price_table import ensure_price_table

if TYPE_CHECKING:
    from app.infrastructure.seed.demo_seed import SeedReport

SEED_PREFIX = "FAT-"
LEFT_UNBILLED_SHARE = 0.25  # pacientes cujos atendimentos ficam para faturar na demonstração
COVERAGES = [Decimal(60), Decimal(70), Decimal(80)]
PATIENT_METHODS = [PaymentMethod.PIX, PaymentMethod.CARD, PaymentMethod.CASH]


class _Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


async def seed_finance(session: AsyncSession, rng: random.Random, report: "SeedReport", now: datetime) -> None:
    await ensure_price_table(session)
    if await session.scalar(select(func.count()).select_from(InvoiceModel)
                            .where(InvoiceModel.invoice_number.like(f"{SEED_PREFIX}%"))):
        report.add("invoices", created=False)
        return

    clock = _Clock(now)
    finance = FinanceUseCase(SQLAlchemyBillingRepository(session), SQLAlchemyFinanceQueries(session),
                             build_publisher(session), clock)
    patients = (await session.scalars(select(PatientModel).order_by(PatientModel.cpf))).all()
    for patient in patients:
        services = await finance.unbilled(patient.id)
        if not services or rng.random() < LEFT_UNBILLED_SHARE:
            continue
        by_month = defaultdict(list)
        for service in services:
            by_month[f"{service.performed_at:%Y-%m}"].append(service)
        coverage = rng.choice(COVERAGES) if patient.insurance_provider else Decimal(0)

        for month in sorted(by_month):
            group = by_month[month]
            issued_at = max(s.performed_at for s in group) + timedelta(days=rng.randint(1, 5))
            if issued_at >= now:
                continue  # atendimentos recentes ficam para faturar
            clock.now = issued_at
            invoice = await finance.invoice_services(patient.id, InvoiceFromServicesDTO(
                services=[ServiceRefDTO(source_type=s.source_type, source_id=s.source_id) for s in group],
                insurance_provider=patient.insurance_provider if coverage else None, coverage_percentage=coverage))
            report.add("invoices", created=True)
            await _settle(finance, clock, rng, report, invoice, now)


async def _settle(finance, clock, rng, report, invoice, now) -> None:
    """Destino de cada fatura: cancelada, quitada, parcialmente paga ou em aberto (às vezes vencida)."""
    outcome = rng.random()
    clock.now = invoice.issue_date + timedelta(days=rng.randint(1, 20))
    if clock.now >= now:
        return
    if outcome < 0.05:
        await finance.cancel(invoice.id, "Lançamento em duplicidade (demonstração).")
        report.add("invoice_cancellations", created=True)
        return
    if outcome >= 0.75:
        return  # em aberto

    payments = []
    if invoice.insurance_share > 0:
        payments.append((invoice.insurance_share, PaymentMethod.INSURANCE))
    if outcome < 0.60:  # quitada
        payments.append((invoice.patient_share, rng.choice(PATIENT_METHODS)))
    elif not payments:  # parcial, particular: metade do valor
        payments.append(((invoice.balance / 2).quantize(CENTS), rng.choice(PATIENT_METHODS)))
    for amount, method in payments:
        if amount > 0:
            await finance.register_payment(invoice.id, amount, method, None)
            report.add("invoice_payments", created=True)
            clock.now += timedelta(days=rng.randint(0, 3))
