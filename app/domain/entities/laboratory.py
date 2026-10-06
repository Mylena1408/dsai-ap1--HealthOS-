"""Laboratório didático: catálogo de exames, solicitações e resultados fictícios.

    SOLICITADO ─► AGENDADO ─► COLETADO ─► EM_PROCESSAMENTO ─► RESULTADO_REGISTRADO ─► VALIDADO ─► LIBERADO
       │  │          │ ▲ │                      ▲                       │
       │  └──────────┼─┘ │ (reagendar)          └── devolvido p/ correção ┘
       │             │   │
       └─────────────┴───┴─► CANCELADO   (apenas antes da coleta)

A coleta pode ocorrer direto da solicitação (coleta imediata, sem agendamento).
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from app.domain.entities.reference_range import ReferenceRange, ResultFlag
from app.domain.exceptions.common import BusinessRuleViolation, InvalidTransitionError


class ExamCategory(Enum):
    HEMATOLOGY = "HEMATOLOGIA"
    BIOCHEMISTRY = "BIOQUIMICA"
    HORMONES = "HORMONIOS"
    VITAMINS = "VITAMINAS"


class SampleType(Enum):
    BLOOD = "SANGUE"
    URINE = "URINA"
    OTHER = "OUTRO"


class ExamPriority(Enum):
    ROUTINE = "ROTINA"
    URGENT = "URGENTE"


class ExamStatus(Enum):
    REQUESTED = "SOLICITADO"
    SCHEDULED = "AGENDADO"
    COLLECTED = "COLETADO"
    PROCESSING = "EM_PROCESSAMENTO"
    RESULTED = "RESULTADO_REGISTRADO"
    VALIDATED = "VALIDADO"
    RELEASED = "LIBERADO"
    CANCELLED = "CANCELADO"


EXAM_TRANSITIONS: dict[ExamStatus, set[ExamStatus]] = {
    ExamStatus.REQUESTED: {ExamStatus.SCHEDULED, ExamStatus.COLLECTED, ExamStatus.CANCELLED},
    ExamStatus.SCHEDULED: {ExamStatus.SCHEDULED, ExamStatus.COLLECTED, ExamStatus.CANCELLED},
    ExamStatus.COLLECTED: {ExamStatus.PROCESSING},
    ExamStatus.PROCESSING: {ExamStatus.RESULTED},
    ExamStatus.RESULTED: {ExamStatus.VALIDATED, ExamStatus.PROCESSING},
    ExamStatus.VALIDATED: {ExamStatus.RELEASED},
    ExamStatus.RELEASED: set(),
    ExamStatus.CANCELLED: set(),
}


@dataclass
class Laboratory:
    """Laboratório (fictício) que executa os exames."""
    name: str
    address: Optional[str] = None
    id: Optional[uuid.UUID] = None


@dataclass
class Analyte:
    code: str
    name: str
    reference: ReferenceRange
    decimals: int = 1
    id: Optional[uuid.UUID] = None


@dataclass
class ExamType:
    code: str
    name: str
    category: ExamCategory
    sample_type: SampleType
    turnaround_hours: int
    analytes: list[Analyte] = field(default_factory=list)
    preparation: Optional[str] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        if not self.analytes:
            raise BusinessRuleViolation(f"O exame {self.code} precisa de pelo menos um analito.")
        codes = [a.code for a in self.analytes]
        if len(codes) != len(set(codes)):
            raise BusinessRuleViolation(f"O exame {self.code} tem analitos repetidos.")

    def analyte(self, code: str) -> Analyte:
        for analyte in self.analytes:
            if analyte.code == code:
                return analyte
        raise BusinessRuleViolation(f"O analito '{code}' não pertence ao exame {self.code}.")


@dataclass
class ExamResult:
    """Valor de um analito. Unidade e referência são copiadas no momento do registro,
    para que mudanças futuras no catálogo não alterem resultados antigos."""
    analyte_code: str
    analyte_name: str
    value: float
    unit: str
    reference_text: str
    flag: ResultFlag


@dataclass
class ExamStatusChange:
    from_status: Optional[ExamStatus]
    to_status: ExamStatus
    changed_at: datetime
    note: Optional[str] = None
    id: Optional[uuid.UUID] = None


@dataclass
class ExamRequest:
    patient_id: uuid.UUID
    exam_type_id: uuid.UUID
    requested_at: datetime
    requested_by: Optional[uuid.UUID] = None  # profissional solicitante
    appointment_id: Optional[uuid.UUID] = None
    laboratory_id: Optional[uuid.UUID] = None
    priority: ExamPriority = ExamPriority.ROUTINE
    clinical_indication: Optional[str] = None
    status: ExamStatus = ExamStatus.REQUESTED
    scheduled_for: Optional[datetime] = None
    sample_code: Optional[str] = None
    collected_at: Optional[datetime] = None
    results: list[ExamResult] = field(default_factory=list)
    result_notes: Optional[str] = None
    resulted_at: Optional[datetime] = None
    validated_by: Optional[uuid.UUID] = None
    validated_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    history: list[ExamStatusChange] = field(default_factory=list)
    id: Optional[uuid.UUID] = None

    @property
    def has_abnormal_results(self) -> bool:
        return any(r.flag.is_abnormal for r in self.results)

    @property
    def has_critical_results(self) -> bool:
        return any(r.flag.is_critical for r in self.results)

    def allowed_transitions(self) -> list[ExamStatus]:
        order = list(ExamStatus)
        return sorted(EXAM_TRANSITIONS[self.status], key=order.index)

    def register_creation(self) -> None:
        self._record(None, ExamStatus.REQUESTED, self.requested_at, "Exame solicitado")

    # ------------------------------------------------------------ transições

    def schedule(self, scheduled_for: datetime, now: datetime) -> None:
        if scheduled_for <= now:
            raise BusinessRuleViolation("A coleta deve ser agendada para um horário futuro.")
        previous = self.scheduled_for
        self._transition(ExamStatus.SCHEDULED, now,
                         f"Coleta {'reagendada' if previous else 'agendada'} para {scheduled_for:%d/%m/%Y %H:%M}")
        self.scheduled_for = scheduled_for

    def collect(self, now: datetime) -> None:
        self._transition(ExamStatus.COLLECTED, now)
        self.collected_at = now
        # Código da amostra (etiqueta do tubo): data da coleta + trecho do id da solicitação.
        self.sample_code = f"AM{now:%Y%m%d}-{str(self.id or uuid.uuid4()).replace('-', '')[:6].upper()}"

    def start_processing(self, now: datetime) -> None:
        self._transition(ExamStatus.PROCESSING, now)

    def record_results(self, exam_type: ExamType, values: dict[str, float], now: datetime,
                       notes: Optional[str] = None) -> None:
        if self.status != ExamStatus.PROCESSING:
            raise InvalidTransitionError("Exame", self.status.value, ExamStatus.RESULTED.value)
        expected = {a.code for a in exam_type.analytes}
        missing, unknown = expected - values.keys(), values.keys() - expected
        if missing:
            raise BusinessRuleViolation(f"Faltam resultados para: {', '.join(sorted(missing))}.")
        if unknown:
            raise BusinessRuleViolation(f"Analitos que não pertencem ao exame: {', '.join(sorted(unknown))}.")

        results = []
        for analyte in exam_type.analytes:
            value = round(float(values[analyte.code]), analyte.decimals)
            analyte.reference.validate(value, analyte.name)
            results.append(ExamResult(
                analyte_code=analyte.code, analyte_name=analyte.name, value=value, unit=analyte.reference.unit,
                reference_text=analyte.reference.describe(), flag=analyte.reference.classify(value)))
        self._transition(ExamStatus.RESULTED, now)
        self.results, self.result_notes, self.resulted_at = results, notes, now

    def validate(self, professional_id: uuid.UUID, now: datetime) -> None:
        self._transition(ExamStatus.VALIDATED, now)
        self.validated_by, self.validated_at = professional_id, now

    def return_for_correction(self, reason: str, now: datetime) -> None:
        """O validador devolve o laudo para reprocessamento; os resultados anteriores são descartados."""
        if self.status != ExamStatus.RESULTED:
            raise InvalidTransitionError("Exame", self.status.value, "DEVOLVIDO")
        if not reason or len(reason.strip()) < 3:
            raise BusinessRuleViolation("Informe o motivo da devolução (mínimo de 3 caracteres).")
        self._transition(ExamStatus.PROCESSING, now, f"Devolvido para correção: {reason.strip()}")
        self.results, self.resulted_at = [], None

    def release(self, now: datetime) -> None:
        self._transition(ExamStatus.RELEASED, now)
        self.released_at = now

    def cancel(self, reason: str, now: datetime) -> None:
        if not reason or len(reason.strip()) < 3:
            raise BusinessRuleViolation("Informe o motivo do cancelamento (mínimo de 3 caracteres).")
        self._transition(ExamStatus.CANCELLED, now, reason.strip())
        self.cancellation_reason = reason.strip()

    # --------------------------------------------------------------- interno

    def _transition(self, target: ExamStatus, now: datetime, note: Optional[str] = None) -> None:
        if target not in EXAM_TRANSITIONS[self.status]:
            raise InvalidTransitionError("Exame", self.status.value, target.value)
        self._record(self.status, target, now, note)
        self.status = target

    def _record(self, from_status, to_status, now, note=None) -> None:
        self.history.append(ExamStatusChange(from_status, to_status, now, note))
