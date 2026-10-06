"""Registro de sinais vitais com classificação didática de cada medida."""
from dataclasses import dataclass, fields
from datetime import date, datetime
from enum import Enum
from typing import Optional
import uuid

from app.domain.entities.reference_range import ReferenceRange, ResultFlag
from app.domain.exceptions.common import BusinessRuleViolation


class VitalMetric(Enum):
    SYSTOLIC = "systolic"
    DIASTOLIC = "diastolic"
    HEART_RATE = "heart_rate"
    RESPIRATORY_RATE = "respiratory_rate"
    TEMPERATURE = "temperature"
    OXYGEN_SATURATION = "oxygen_saturation"
    WEIGHT = "weight_kg"
    HEIGHT = "height_cm"
    GLUCOSE = "glucose_mg_dl"
    BMI = "bmi"


METRIC_LABELS = {
    VitalMetric.SYSTOLIC: "Pressão sistólica", VitalMetric.DIASTOLIC: "Pressão diastólica",
    VitalMetric.HEART_RATE: "Frequência cardíaca", VitalMetric.RESPIRATORY_RATE: "Frequência respiratória",
    VitalMetric.TEMPERATURE: "Temperatura", VitalMetric.OXYGEN_SATURATION: "Saturação de O₂",
    VitalMetric.WEIGHT: "Peso", VitalMetric.HEIGHT: "Altura", VitalMetric.GLUCOSE: "Glicemia capilar",
    VitalMetric.BMI: "IMC",
}

# Faixas ilustrativas para adultos (ver reference_range.py).
VITAL_RANGES: dict[VitalMetric, ReferenceRange] = {
    VitalMetric.SYSTOLIC: ReferenceRange("mmHg", 40, 300, 90, 129, 70, 180),
    VitalMetric.DIASTOLIC: ReferenceRange("mmHg", 20, 200, 60, 84, 40, 120),
    VitalMetric.HEART_RATE: ReferenceRange("bpm", 20, 250, 60, 100, 40, 130),
    VitalMetric.RESPIRATORY_RATE: ReferenceRange("irpm", 4, 80, 12, 20, 8, 30),
    VitalMetric.TEMPERATURE: ReferenceRange("°C", 30, 45, 35.5, 37.7, 34, 40),
    VitalMetric.OXYGEN_SATURATION: ReferenceRange("%", 50, 100, 95, None, 90, None),
    VitalMetric.WEIGHT: ReferenceRange("kg", 0.5, 400),
    VitalMetric.HEIGHT: ReferenceRange("cm", 30, 250),
    VitalMetric.GLUCOSE: ReferenceRange("mg/dL", 10, 1000, 70, 99, 54, 300),
    VitalMetric.BMI: ReferenceRange("kg/m²", 5, 100, 18.5, 24.9, None, None),
}


class BmiCategory(Enum):
    UNDERWEIGHT = "BAIXO_PESO"
    NORMAL = "PESO_ADEQUADO"
    OVERWEIGHT = "SOBREPESO"
    OBESITY = "OBESIDADE"


def bmi_category(bmi: float) -> BmiCategory:
    """Classificação didática do IMC para adultos."""
    if bmi < 18.5:
        return BmiCategory.UNDERWEIGHT
    if bmi < 25:
        return BmiCategory.NORMAL
    if bmi < 30:
        return BmiCategory.OVERWEIGHT
    return BmiCategory.OBESITY


@dataclass
class VitalSigns:
    patient_id: uuid.UUID
    recorded_at: datetime
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
    notes: Optional[str] = None
    id: Optional[uuid.UUID] = None

    def __post_init__(self):
        measured = self.measurements()
        if not measured:
            raise BusinessRuleViolation("Informe ao menos uma medida.")
        for metric, value in measured.items():
            VITAL_RANGES[metric].validate(value, METRIC_LABELS[metric])
        if (self.systolic is None) != (self.diastolic is None):
            raise BusinessRuleViolation("A pressão arterial exige os valores sistólico e diastólico.")
        if self.systolic is not None and self.systolic <= self.diastolic:
            raise BusinessRuleViolation("A pressão sistólica deve ser maior que a diastólica.")

    def validate_date(self, now: datetime, birth_date: date) -> None:
        if self.recorded_at > now:
            raise BusinessRuleViolation("A data da medição não pode estar no futuro.")
        if self.recorded_at.date() < birth_date:
            raise BusinessRuleViolation("A data da medição não pode ser anterior ao nascimento.")

    def measurements(self) -> dict[VitalMetric, float]:
        """Medidas efetivamente informadas neste registro (sem o IMC, que é derivado)."""
        names = {f.name for f in fields(self)}
        return {m: getattr(self, m.value) for m in VitalMetric
                if m.value in names and getattr(self, m.value) is not None}

    def bmi(self, fallback_height_cm: Optional[float] = None) -> Optional[float]:
        """IMC com o peso deste registro e a altura dele (ou a última altura conhecida)."""
        height = self.height_cm or fallback_height_cm
        if self.weight_kg is None or not height:
            return None
        return round(self.weight_kg / (height / 100) ** 2, 1)

    def flags(self, fallback_height_cm: Optional[float] = None) -> dict[VitalMetric, ResultFlag]:
        result = {m: VITAL_RANGES[m].classify(v) for m, v in self.measurements().items()
                  if VITAL_RANGES[m].normal_min is not None or VITAL_RANGES[m].normal_max is not None}
        bmi = self.bmi(fallback_height_cm)
        if bmi is not None:
            result[VitalMetric.BMI] = VITAL_RANGES[VitalMetric.BMI].classify(bmi)
        return result
