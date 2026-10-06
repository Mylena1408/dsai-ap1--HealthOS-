from bisect import bisect_right
from datetime import datetime
from typing import Callable, Optional
import uuid

from app.application.dtos.clinical_monitoring_dto import (
    MetricSummaryDTO, VitalSignsCreateDTO, VitalSignsDTO, VitalSignsSummaryDTO,
)
from app.application.dtos.common import Page
from app.application.interfaces.clinical_monitoring_repository import VitalSignsRepository
from app.application.interfaces.medical_record_repository import PatientDirectoryRepository
from app.application.interfaces.professional_repository import ProfessionalRepository
from app.domain.entities.vital_signs import (
    METRIC_LABELS, VITAL_RANGES, VitalMetric, VitalSigns, bmi_category,
)
from app.domain.exceptions.common import EntityNotFoundError

SERIES_LENGTH = 30
# Variação mínima (relativa) para considerar que a medida subiu ou desceu.
TREND_TOLERANCE = 0.02


def trend(previous: Optional[float], latest: float) -> Optional[str]:
    if previous is None:
        return None
    if previous == 0 or abs(latest - previous) / abs(previous) <= TREND_TOLERANCE:
        return "ESTAVEL"
    return "SUBINDO" if latest > previous else "DESCENDO"


class VitalSignsUseCase:

    def __init__(self, repo: VitalSignsRepository, directory: PatientDirectoryRepository,
                 professional_repo: ProfessionalRepository, clock: Callable[[], datetime] = datetime.now):
        self.repo = repo
        self.directory = directory
        self.professional_repo = professional_repo
        self.clock = clock

    async def record(self, patient_id: uuid.UUID, dto: VitalSignsCreateDTO) -> VitalSignsDTO:
        patient = await self.directory.get(patient_id)
        if not patient:
            raise EntityNotFoundError("Paciente", patient_id)
        if dto.professional_id and not await self.professional_repo.get_by_id(dto.professional_id):
            raise EntityNotFoundError("Profissional", dto.professional_id)

        now = self.clock()
        data = dto.model_dump(exclude={"recorded_at"})
        recorded_at = (dto.recorded_at or now).replace(tzinfo=None, microsecond=0)
        vitals = VitalSigns(patient_id=patient_id, recorded_at=recorded_at, **data)
        vitals.validate_date(now, patient.birth_date)
        saved = await self.repo.save(vitals)
        return self._to_dto(saved, await self.repo.last_height(patient_id, saved.recorded_at))

    async def page(self, patient_id: uuid.UUID, date_from: Optional[datetime], date_to: Optional[datetime],
                   limit: int, offset: int) -> Page[VitalSignsDTO]:
        await self._ensure_patient(patient_id)
        items, total = await self.repo.page(patient_id, date_from, date_to, limit, offset)
        # A altura de referência para o IMC é a última conhecida até cada medição. O histórico
        # de alturas é lido uma única vez (evita uma consulta por registro).
        heights = await self.repo.height_history(patient_id)
        moments = [moment for moment, _ in heights]

        def height_at(moment: datetime) -> Optional[float]:
            index = bisect_right(moments, moment)
            return heights[index - 1][1] if index else None

        dtos = [self._to_dto(v, height_at(v.recorded_at)) for v in items]
        return Page(items=dtos, total=total, limit=limit, offset=offset)

    async def summary(self, patient_id: uuid.UUID) -> VitalSignsSummaryDTO:
        await self._ensure_patient(patient_id)
        history = await self.repo.history(patient_id, SERIES_LENGTH)

        series: dict[VitalMetric, list[tuple[datetime, float]]] = {}
        last_height = None
        for record in history:  # ordem cronológica
            last_height = record.height_cm or last_height
            values = dict(record.measurements())
            bmi = record.bmi(last_height)
            if bmi is not None:
                values[VitalMetric.BMI] = bmi
            for metric, value in values.items():
                series.setdefault(metric, []).append((record.recorded_at, value))

        metrics = []
        for metric in VitalMetric:
            points = series.get(metric)
            if not points:
                continue
            reference = VITAL_RANGES[metric]
            has_range = reference.normal_min is not None or reference.normal_max is not None
            latest_at, latest = points[-1]
            previous = points[-2][1] if len(points) > 1 else None
            metrics.append(MetricSummaryDTO(
                metric=metric, label=METRIC_LABELS[metric], unit=reference.unit,
                reference=reference.describe() if has_range else None,
                normal_min=reference.normal_min, normal_max=reference.normal_max,
                latest=latest, latest_at=latest_at, flag=reference.classify(latest) if has_range else None,
                previous=previous, trend=trend(previous, latest), series=points,
            ))
        return VitalSignsSummaryDTO(patient_id=patient_id, records=len(history), metrics=metrics)

    async def _ensure_patient(self, patient_id: uuid.UUID) -> None:
        if not await self.directory.get(patient_id):
            raise EntityNotFoundError("Paciente", patient_id)

    @staticmethod
    def _to_dto(v: VitalSigns, fallback_height: Optional[float]) -> VitalSignsDTO:
        bmi = v.bmi(fallback_height)
        return VitalSignsDTO(
            id=v.id, recorded_at=v.recorded_at, professional_id=v.professional_id, notes=v.notes,
            **{m.value: getattr(v, m.value) for m in VitalMetric if m != VitalMetric.BMI},
            bmi=bmi, bmi_category=bmi_category(bmi) if bmi is not None else None,
            flags=v.flags(fallback_height),
        )
