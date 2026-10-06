"""Faixas de referência ILUSTRATIVAS usadas por sinais vitais e exames.

Os valores são simplificados para fins didáticos (adulto genérico, sem distinção
por sexo, idade ou método) e não devem ser usados para interpretação clínica real.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.domain.exceptions.common import BusinessRuleViolation


class ResultFlag(Enum):
    NORMAL = "NORMAL"
    LOW = "BAIXO"
    HIGH = "ALTO"
    CRITICAL_LOW = "CRITICO_BAIXO"
    CRITICAL_HIGH = "CRITICO_ALTO"

    @property
    def is_abnormal(self) -> bool:
        return self != ResultFlag.NORMAL

    @property
    def is_critical(self) -> bool:
        return self in (ResultFlag.CRITICAL_LOW, ResultFlag.CRITICAL_HIGH)


@dataclass(frozen=True)
class ReferenceRange:
    """
    normal_min/normal_max: limites da faixa esperada (None = sem limite daquele lado).
    critical_min/critical_max: valores que exigem atenção imediata (didático).
    plausible_min/plausible_max: fora disso o valor é considerado erro de digitação.
    """
    unit: str
    plausible_min: float
    plausible_max: float
    normal_min: Optional[float] = None
    normal_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None

    def validate(self, value: float, label: str) -> None:
        if not self.plausible_min <= value <= self.plausible_max:
            raise BusinessRuleViolation(
                f"{label}: {value} {self.unit} está fora dos limites aceitáveis "
                f"({self.plausible_min}–{self.plausible_max} {self.unit})."
            )

    def classify(self, value: float) -> ResultFlag:
        if self.critical_min is not None and value < self.critical_min:
            return ResultFlag.CRITICAL_LOW
        if self.critical_max is not None and value > self.critical_max:
            return ResultFlag.CRITICAL_HIGH
        if self.normal_min is not None and value < self.normal_min:
            return ResultFlag.LOW
        if self.normal_max is not None and value > self.normal_max:
            return ResultFlag.HIGH
        return ResultFlag.NORMAL

    def describe(self) -> str:
        if self.normal_min is not None and self.normal_max is not None:
            return f"{self.normal_min:g}–{self.normal_max:g} {self.unit}"
        if self.normal_min is not None:
            return f"≥ {self.normal_min:g} {self.unit}"
        if self.normal_max is not None:
            return f"≤ {self.normal_max:g} {self.unit}"
        return self.unit
