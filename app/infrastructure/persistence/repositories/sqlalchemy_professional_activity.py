from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.professional_activity import ActivityItem, ActivityKind, ProfessionalActivityQueries
from app.application.services.code_labels import code_label
from app.infrastructure.persistence.models.appointment_model import AppointmentModel
from app.infrastructure.persistence.models.clinical_monitoring_model import (
    ExamRequestModel, ExamTypeModel, VitalSignsModel,
)
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.models.pharmacy_model import DispensationModel, PrescriptionModel


def _vitals_text(v: VitalSignsModel) -> str:
    parts = []
    if v.systolic and v.diastolic:
        parts.append(f"PA {v.systolic}/{v.diastolic} mmHg")
    if v.heart_rate:
        parts.append(f"FC {v.heart_rate} bpm")
    if v.oxygen_saturation:
        parts.append(f"SpO2 {v.oxygen_saturation}%")
    if v.temperature:
        parts.append(f"{v.temperature:.1f} °C")
    return "Sinais vitais registrados" + (f": {', '.join(parts)}" if parts else "")


# Para cada tipo: modelo, coluna do profissional, coluna de data e texto de cada registro.
SOURCES = {
    ActivityKind.APPOINTMENT: (AppointmentModel, AppointmentModel.professional_id, AppointmentModel.start_time,
                               lambda a, extra: f"Consulta ({code_label(a.appointment_type).lower()}) — {code_label(a.status).lower()}"),
    ActivityKind.VITAL_SIGNS: (VitalSignsModel, VitalSignsModel.professional_id, VitalSignsModel.recorded_at,
                               lambda v, extra: _vitals_text(v)),
    ActivityKind.PRESCRIPTION: (PrescriptionModel, PrescriptionModel.prescriber_id, PrescriptionModel.issued_at,
                                lambda p, extra: f"Prescrição emitida — {code_label(p.status).lower()}"),
    ActivityKind.DISPENSATION: (DispensationModel, DispensationModel.pharmacist_id, DispensationModel.dispensed_at,
                                lambda d, extra: f"Medicamentos dispensados ({code_label(d.location)})"),
    ActivityKind.EXAM_REQUESTED: (ExamRequestModel, ExamRequestModel.requested_by, ExamRequestModel.requested_at,
                                  lambda e, extra: f"Exame solicitado: {extra}"),
    ActivityKind.EXAM_VALIDATED: (ExamRequestModel, ExamRequestModel.validated_by, ExamRequestModel.validated_at,
                                  lambda e, extra: f"Exame validado: {extra}"),
}


class SQLAlchemyProfessionalActivity(ProfessionalActivityQueries):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def totals(self, professional_id, until):
        result = {}
        for kind, (model, column, moment, _) in SOURCES.items():
            result[kind] = await self.session.scalar(
                select(func.count()).select_from(model).where(column == professional_id, moment <= until))
        return result

    async def recent(self, professional_id, until, limit):
        items: list[ActivityItem] = []
        for kind, (model, column, moment, describe) in SOURCES.items():
            stmt = (select(model, PatientModel.full_name, *([ExamTypeModel.name] if model is ExamRequestModel else []))
                    .join(PatientModel, PatientModel.id == model.patient_id)
                    .where(column == professional_id, moment <= until))
            if model is ExamRequestModel:
                stmt = stmt.join(ExamTypeModel, ExamTypeModel.id == ExamRequestModel.exam_type_id)
            for row in (await self.session.execute(stmt.order_by(moment.desc()).limit(limit))).all():
                record, patient_name, *extra = row
                items.append(ActivityItem(kind=kind, occurred_at=getattr(record, moment.key),
                                          description=describe(record, extra[0] if extra else None),
                                          patient_id=record.patient_id, patient_name=patient_name))
        return sorted(items, key=lambda i: i.occurred_at, reverse=True)[:limit]
