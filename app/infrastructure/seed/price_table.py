"""Tabela de preços FICTÍCIA (dado de referência, garantido no startup).

Valores ilustrativos para demonstrar o faturamento; não correspondem a nenhuma tabela real.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.billing import (
    DEFAULT_EXAM_PRICE_CODE, BillingType, appointment_price_code, exam_price_code,
)
from app.infrastructure.persistence.models.finance_model import ServicePriceModel


PRICE_TABLE = [
    (appointment_price_code("PRIMEIRA_CONSULTA"), "Consulta — primeira consulta", BillingType.CONSULTATION, "250.00"),
    (appointment_price_code("RETORNO"), "Consulta — retorno", BillingType.CONSULTATION, "150.00"),
    (appointment_price_code("URGENCIA"), "Consulta — urgência", BillingType.URGENCY_FEE, "350.00"),
    (appointment_price_code("TELECONSULTA"), "Teleconsulta", BillingType.CONSULTATION, "120.00"),
    (exam_price_code("HEMO"), "Hemograma", BillingType.EXAM, "35.00"),
    (exam_price_code("GLI"), "Glicemia de jejum", BillingType.EXAM, "15.00"),
    (exam_price_code("HBA1C"), "Hemoglobina glicada", BillingType.EXAM, "40.00"),
    (exam_price_code("LIPID"), "Perfil lipídico", BillingType.EXAM, "55.00"),
    (exam_price_code("TG"), "Triglicerídeos", BillingType.EXAM, "18.00"),
    (exam_price_code("CREA"), "Creatinina", BillingType.EXAM, "16.00"),
    (exam_price_code("UREIA"), "Ureia", BillingType.EXAM, "16.00"),
    (exam_price_code("K"), "Potássio", BillingType.EXAM, "18.00"),
    (exam_price_code("TSH"), "TSH", BillingType.EXAM, "45.00"),
    (exam_price_code("T4L"), "T4 livre", BillingType.EXAM, "45.00"),
    (exam_price_code("VITD"), "Vitamina D (25-OH)", BillingType.EXAM, "90.00"),
    (DEFAULT_EXAM_PRICE_CODE, "Exame laboratorial (preço padrão)", BillingType.EXAM, "30.00"),
]


async def ensure_price_table(session: AsyncSession) -> int:
    """Insere os preços que faltam; não altera preços já cadastrados. Devolve quantos foram criados."""
    existing = set(await session.scalars(select(ServicePriceModel.code)))
    created = 0
    for code, description, billing_type, price in PRICE_TABLE:
        if code not in existing:
            session.add(ServicePriceModel(code=code, description=description, billing_type=billing_type.value,
                                          price=Decimal(price), active=True))
            created += 1
    await session.flush()
    return created
