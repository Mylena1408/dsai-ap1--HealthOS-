from datetime import date, datetime
from typing import Optional
import uuid

from pydantic import BaseModel

from app.application.dtos.appointment_dto import AppointmentResponseDTO
from app.application.dtos.clinical_monitoring_dto import ExamRequestDTO, MetricSummaryDTO
from app.application.dtos.engagement_dto import SystemAlertDTO
from app.application.dtos.pharmacy_dto import PatientMedicationDTO
from app.domain.services.health_score import ScoreBand


class ScoreComponentDTO(BaseModel):
    key: str
    label: str
    score: Optional[int]
    applicable: bool
    explanation: str


class HealthScoreDTO(BaseModel):
    patient_id: uuid.UUID
    score: Optional[int]
    band: Optional[ScoreBand]
    components: list[ScoreComponentDTO]
    computed_at: datetime
    disclaimer: str


class DailyPoint(BaseModel):
    day: date
    values: dict[str, float]


class RankedItem(BaseModel):
    label: str
    value: float


class PatientDashboardDTO(BaseModel):
    patient_id: uuid.UUID
    patient_name: str
    age: int
    health_score: HealthScoreDTO
    upcoming_appointments: list[AppointmentResponseDTO]
    medications_in_use: list[PatientMedicationDTO]
    recent_exams: list[ExamRequestDTO]
    vitals: list[MetricSummaryDTO]
    open_alerts: list[SystemAlertDTO]
    unread_notifications: int


class ProfessionalDashboardDTO(BaseModel):
    professional_id: uuid.UUID
    professional_name: str
    today: list[AppointmentResponseDTO]
    next_7_days: int
    appointments_30d: dict[str, int]
    patients_seen_30d: int
    attendance_rate_30d: Optional[float]
    exams_requested: dict[str, int]
    recent_abnormal_exams: list[ExamRequestDTO]
    daily_30d: list[DailyPoint]
    unread_notifications: int


class PharmacyDashboardDTO(BaseModel):
    items_below_minimum: int
    zero_stock: int
    lots_expiring_30d: int
    lots_expired: int
    dispensation_queue: int
    units_dispensed_30d: float
    daily_30d: list[DailyPoint]
    top_medications_30d: list[RankedItem]
    open_alerts: list[SystemAlertDTO]


class AdminDashboardDTO(BaseModel):
    counts: dict[str, int]
    appointments_30d: dict[str, int]
    daily_appointments_30d: list[DailyPoint]
    exams_90d: dict[str, int]
    prescriptions_30d: dict[str, int]
    alerts_open: dict[str, dict[str, int]]
    new_patients_monthly: list[RankedItem]
    health_score_distribution: dict[str, int]
    health_score_average: Optional[float]
