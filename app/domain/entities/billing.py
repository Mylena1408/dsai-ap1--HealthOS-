from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.exceptions.common import BusinessRuleViolation, ConflictError, InvalidTransitionError

CENTS = Decimal("0.01")
DEFAULT_DUE_DAYS = 15

class BillingStatus(Enum):
    """Status do ciclo de vida de uma fatura."""
    DRAFT = "RASCUNHO"
    PENDING = "PENDENTE"
    PAID = "PAGO"
    PARTIALLY_PAID = "PARCIALMENTE_PAGO"
    OVERDUE = "ATRASADO"
    CANCELLED = "CANCELADO"

# Situações em que ainda há valor a receber.
OPEN_STATUSES = frozenset({BillingStatus.PENDING, BillingStatus.PARTIALLY_PAID, BillingStatus.OVERDUE})


class BillingType(Enum):
    """Tipo de cobrança do serviço hospitalar."""
    CONSULTATION = "CONSULTA"
    EXAM = "EXAME"
    PROCEDURE = "PROCEDIMENTO"
    MEDICATION = "MEDICAMENTO"
    ROOM_STAY = "DIÁRIA_QUARTO"
    URGENCY_FEE = "TAXA_URGENCIA"


class PaymentMethod(Enum):
    PIX = "PIX"
    CARD = "CARTAO"
    CASH = "DINHEIRO"
    INSURANCE = "CONVENIO"  # repasse do convênio
    UNSPECIFIED = "NAO_INFORMADO"  # pagamentos registrados pela rota antiga, sem forma de pagamento


class ServiceSource(Enum):
    """Atendimento que originou um item faturado (impede cobrar o mesmo serviço duas vezes)."""
    APPOINTMENT = "CONSULTA"
    EXAM = "EXAME"



# Códigos da tabela de preços para cada serviço faturável.
DEFAULT_EXAM_PRICE_CODE = "EXAME-PADRAO"


def appointment_price_code(appointment_type: str) -> str:
    return f"CONSULTA-{appointment_type}"


def exam_price_code(exam_code: str) -> str:
    return f"EXAME-{exam_code}"


@dataclass
class Payment:
    amount: Decimal
    method: PaymentMethod
    paid_at: datetime
    note: Optional[str] = None
    id: Optional[uuid.UUID] = None

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
    source_type: Optional[ServiceSource] = None
    source_id: Optional[uuid.UUID] = None

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
    insurance_coverage_percentage: Decimal = Decimal("0.00") # percentual de 0 a 100 (ex.: 80)
    payments: List[Payment] = field(default_factory=list)
    cancellation_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None

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

    # ------------------------------------------------------------------ ciclo de vida

    def amount_paid(self) -> Decimal:
        return sum((p.amount for p in self.payments), Decimal("0.00"))

    def balance(self) -> Decimal:
        """Valor ainda em aberto (convênio + paciente)."""
        return (self.calculate_gross_total() - self.amount_paid()).quantize(CENTS)

    def effective_status(self, now: datetime) -> BillingStatus:
        """ATRASADO é derivado do vencimento: não depende de um processo que atualize o banco."""
        if self.status in (BillingStatus.PENDING, BillingStatus.PARTIALLY_PAID) and self.due_date and self.due_date < now:
            return BillingStatus.OVERDUE
        return self.status

    def issue(self, now: datetime, due_days: int = DEFAULT_DUE_DAYS) -> None:
        """Fecha o rascunho para cobrança."""
        if self.status != BillingStatus.DRAFT:
            raise InvalidTransitionError("Fatura", self.status.value, BillingStatus.PENDING.value)
        if not self.items:
            raise BusinessRuleViolation("Não é possível finalizar uma fatura sem itens de cobrança.")
        if self.calculate_gross_total() <= 0:
            raise BusinessRuleViolation("O valor total da fatura deve ser maior que zero.")
        self.status = BillingStatus.PENDING
        self.issue_date = now
        self.due_date = now + timedelta(days=due_days)

    def register_payment(self, payment: Payment) -> None:
        if self.status not in OPEN_STATUSES:
            raise ConflictError(f"Fatura {self.status.value.lower()} não recebe pagamentos: só faturas emitidas e não quitadas.")
        amount = Decimal(payment.amount).quantize(CENTS)
        if amount <= 0:
            raise BusinessRuleViolation("O valor do pagamento deve ser maior que zero.")
        if amount > self.balance():
            raise BusinessRuleViolation(f"O pagamento excede o saldo em aberto (R$ {self.balance()}).")
        payment.amount = amount
        self.payments.append(payment)
        self.status = BillingStatus.PAID if self.balance() == 0 else BillingStatus.PARTIALLY_PAID

    def cancel(self, reason: str, now: datetime) -> None:
        reason = (reason or "").strip()
        if self.status in (BillingStatus.PAID, BillingStatus.CANCELLED):
            raise InvalidTransitionError("Fatura", self.status.value, BillingStatus.CANCELLED.value)
        if self.payments:
            raise BusinessRuleViolation("A fatura já tem pagamentos registrados; o estorno não faz parte deste sistema didático.")
        if len(reason) < 3:
            raise BusinessRuleViolation("Informe o motivo do cancelamento.")
        self.status = BillingStatus.CANCELLED
        self.cancellation_reason = reason
        self.cancelled_at = now

