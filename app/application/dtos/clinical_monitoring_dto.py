from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field

from app.domain.entities.laboratory import ExamCategory, ExamPriority, ExamStatus, SampleType
from app.domain.entities.reference_range import ResultFlag
from app.domain.entities.vital_signs import BmiCategory, VitalMetric

DISCLAIMER = ("Valores e faixas de referência ilustrativos, para fins educacionais. "
              "Não substituem avaliação profissional.")


# ------------------------------------------------------------- sinais vitais

class VitalSignsCreateDTO(BaseModel):
    recorded_at: Optional[datetime] = Field(None, description="Padrão: agora")
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    heart_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    temperature: Optional[float] = None
    oxygen_saturation: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    glucose_mg_dl: Optional[int] = None
    professional_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(None, max_length=500)


class VitalSignsDTO(VitalSignsCreateDTO):
    id: uuid.UUID
    recorded_at: datetime
    bmi: Optional[float]
    bmi_category: Optional[BmiCategory]
    flags: dict[VitalMetric, ResultFlag]


class MetricSummaryDTO(BaseModel):
    metric: VitalMetric
    label: str
    unit: str
    reference: Optional[str]
    normal_min: Optional[float]
    normal_max: Optional[float]
    latest: float
    latest_at: datetime
    flag: Optional[ResultFlag]
    previous: Optional[float]
    trend: Optional[str] = Field(None, description="SUBINDO, DESCENDO ou ESTAVEL em relação à medida anterior")
    series: list[tuple[datetime, float]]


class VitalSignsSummaryDTO(BaseModel):
    patient_id: uuid.UUID
    records: int
    metrics: list[MetricSummaryDTO]
    disclaimer: str = DISCLAIMER


# --------------------------------------------------------------- laboratório

class AnalyteDTO(BaseModel):
    code: str
    name: str
    unit: str
    reference: str
    normal_min: Optional[float]
    normal_max: Optional[float]
    decimals: int


class ExamTypeDTO(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: ExamCategory
    sample_type: SampleType
    turnaround_hours: int
    preparation: Optional[str]
    analytes: list[AnalyteDTO]


class LaboratoryDTO(BaseModel):
    id: uuid.UUID
    name: str
    address: Optional[str]


class ExamRequestCreateDTO(BaseModel):
    patient_id: uuid.UUID
    exam_type_id: uuid.UUID
    requested_by: Optional[uuid.UUID] = None
    appointment_id: Optional[uuid.UUID] = None
    laboratory_id: Optional[uuid.UUID] = None
    priority: ExamPriority = ExamPriority.ROUTINE
    clinical_indication: Optional[str] = Field(None, max_length=500)


class ExamScheduleDTO(BaseModel):
    scheduled_for: datetime


class ExamResultsInputDTO(BaseModel):
    values: dict[str, float] = Field(..., description="Código do analito -> valor")
    notes: Optional[str] = Field(None, max_length=2000)


class ExamValidateDTO(BaseModel):
    professional_id: uuid.UUID


class ReasonDTO(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class ExamResultDTO(BaseModel):
    analyte_code: str
    analyte_name: str
    value: float
    unit: str
    reference_text: str
    flag: ResultFlag


class ExamStatusChangeDTO(BaseModel):
    from_status: Optional[ExamStatus]
    to_status: ExamStatus
    changed_at: datetime
    note: Optional[str]


class ExamRequestDTO(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: Optional[str]
    exam_type_id: uuid.UUID
    exam_code: Optional[str]
    exam_name: Optional[str]
    requested_by: Optional[uuid.UUID]
    requested_by_name: Optional[str]
    appointment_id: Optional[uuid.UUID]
    laboratory_id: Optional[uuid.UUID]
    laboratory_name: Optional[str]
    priority: ExamPriority
    clinical_indication: Optional[str]
    status: ExamStatus
    allowed_transitions: list[ExamStatus]
    requested_at: datetime
    scheduled_for: Optional[datetime]
    sample_code: Optional[str]
    collected_at: Optional[datetime]
    expected_by: Optional[datetime] = Field(None, description="Coleta + prazo do exame")
    results: list[ExamResultDTO]
    has_abnormal_results: bool
    has_critical_results: bool
    result_notes: Optional[str]
    validated_by: Optional[uuid.UUID]
    validated_by_name: Optional[str]
    validated_at: Optional[datetime]
    released_at: Optional[datetime]
    cancellation_reason: Optional[str]
    history: list[ExamStatusChangeDTO]


class AnalyteHistoryDTO(BaseModel):
    analyte_code: str
    analyte_name: Optional[str]
    unit: Optional[str]
    reference_text: Optional[str]
    points: list[tuple[datetime, float, ResultFlag]]
    disclaimer: str = DISCLAIMER
