from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import uuid
from datetime import datetime
from decimal import Decimal

class BillingStatus(Enum):
    """Status do ciclo de vida de uma fatura."""
    DRAFT = "RASCUNHO"
    PENDING = "PENDENTE"
    PAID = "PAGO"
    PARTIALLY_PAID = "PARCIALMENTE_PAGO"
    OVERDUE = "ATRASADO"
    CANCELLED = "CANCELADO"

class BillingType(Enum):
    """Tipo de cobrança do serviço hospitalar."""
    CONSULTATION = "CONSULTA"
    EXAM = "EXAME"
    PROCEDURE = "PROCEDIMENTO"
    MEDICATION = "MEDICAMENTO"
    ROOM_STAY = "DIÁRIA_QUARTO"
    URGENCY_FEE = "TAXA_URGENCIA"

@dataclass
class BillingItem:
    """
    Item individual de cobrança dentro de uma fatura.
    """
    id: Optional[uuid.UUID] = None
    description: str = field(default="")
    billing_type: BillingType = field(default=BillingType.CONSULTATION)
    quantity: Decimal = Decimal("1.0")
    unit_price: Decimal = Decimal("0.00")
    discount: Decimal = Decimal("0.00")

    def calculate_total(self) -> Decimal:
        """Calcula o total do item aplicando o desconto."""
        return (self.quantity * self.unit_price) - self.discount

@dataclass
class Invoice:
    """
    Entidade de Domínio Invoice (Fatura).
    Representa a consolidação de todos os custos de um atendimento.
    """
    id: Optional[uuid.UUID] = None
    patient_id: uuid.UUID = field(default=None)
    invoice_number: str = field(default="") # Número fiscal/interno
    issue_date: datetime = field(default_factory=datetime.now)
    due_date: datetime = field(default=None)
    status: BillingStatus = BillingStatus.DRAFT
    items: List[BillingItem] = field(default_factory=list)

    # Informações do Convênio
    insurance_provider: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_coverage_percentage: Decimal = Decimal("0.00") # Ex: 0.80 para 80%

    def add_item(self, item: BillingItem):
        """Adiciona um item de cobrança à fatura."""
        if self.status != BillingStatus.DRAFT:
            raise ValueError("Não é possível adicionar itens a faturas que não estejam em rascunho.")
        self.items.append(item)

    def calculate_gross_total(self) -> Decimal:
        """Calcula o valor total bruto de todos os itens."""
        return sum((item.calculate_total() for item in self.items), Decimal("0.00"))

    def calculate_patient_share(self) -> Decimal:
        """
        Calcula a parte que cabe ao paciente pagar após a cobertura do convênio.
        """
        gross = self.calculate_gross_total()
        coverage = Decimal(str(self.insurance_coverage_percentage)) / Decimal("100")
        return gross * (Decimal("1.00") - coverage)

    def mark_as_paid(self):
        """Transição de estado para Pago."""
        self.status = BillingStatus.PAID
