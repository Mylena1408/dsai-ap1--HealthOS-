from abc import ABC, abstractmethod
from typing import List, Optional
import uuid
from datetime import datetime
from app.domain.entities.billing import Invoice, BillingItem

class BillingRepository(ABC):
    """
    Interface de Repositório para Faturamento.
    """

    @abstractmethod
    async def save_invoice(self, invoice: Invoice) -> Invoice:
        pass

    @abstractmethod
    async def get_invoice_by_id(self, invoice_id: uuid.UUID) -> Optional[Invoice]:
        pass

    @abstractmethod
    async def get_invoices_by_patient(self, patient_id: uuid.UUID) -> List[Invoice]:
        pass

    @abstractmethod
    async def update_invoice_status(self, invoice_id: uuid.UUID, status: str) -> bool:
        pass
