from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.appointment_repository import AppointmentFilters, AppointmentRepository
from app.domain.entities.appointment import (
    ACTIVE_STATUSES, Appointment, AppointmentStatus, AppointmentType, StatusChange,
)
from app.infrastructure.persistence.models.appointment_model import (
    AppointmentModel, AppointmentStatusHistoryModel,
)
from app.infrastructure.persistence.models.patient_model import PatientModel


class SQLAlchemyAppointmentRepository(AppointmentRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, appointment: Appointment) -> Appointment:
        model = await self.session.get(AppointmentModel, appointment.id) if appointment.id else None
        if model is None:
            model = AppointmentModel(id=appointment.id or uuid.uuid4(), history=[])
            if appointment.created_at:  # None explícito gravaria NULL em vez do default
                model.created_at = appointment.created_at
            self.session.add(model)

        model.patient_id = appointment.patient_id
        model.professional_id = appointment.professional_id
        model.specialty_id = appointment.specialty_id
        model.appointment_type = appointment.appointment_type.value
        model.status = appointment.status.value
        model.start_time = appointment.start_time
        model.end_time = appointment.end_time
        model.duration_minutes = appointment.duration_minutes
        model.reason = appointment.reason
        model.notes = appointment.notes
        model.cancellation_reason = appointment.cancellation_reason

        # O histórico é somente acréscimo: grava apenas as mudanças ainda sem id.
        for change in appointment.history:
            if change.id is None:
                change.id = uuid.uuid4()
                model.history.append(AppointmentStatusHistoryModel(
                    id=change.id, from_status=change.from_status.value if change.from_status else None,
                    to_status=change.to_status.value, changed_at=change.changed_at, note=change.note,
                ))

        await self.session.flush()
        appointment.id = model.id
        return appointment

    async def get_by_id(self, appointment_id: uuid.UUID) -> Optional[Appointment]:
        model = await self.session.get(AppointmentModel, appointment_id)
        return self._to_domain(model) if model else None

    async def find_active_overlapping(self, start: datetime, end: datetime, *,
                                      professional_id: Optional[uuid.UUID] = None,
                                      patient_id: Optional[uuid.UUID] = None,
                                      exclude_id: Optional[uuid.UUID] = None) -> list[Appointment]:
        # Sobreposição de intervalos: (inícioA < fimB) e (fimA > inícioB)
        conditions = [
            AppointmentModel.status.in_([s.value for s in ACTIVE_STATUSES]),
            AppointmentModel.start_time < end,
            AppointmentModel.end_time > start,
        ]
        owners = []
        if professional_id:
            owners.append(AppointmentModel.professional_id == professional_id)
        if patient_id:
            owners.append(AppointmentModel.patient_id == patient_id)
        if owners:
            conditions.append(or_(*owners))
        if exclude_id:
            conditions.append(AppointmentModel.id != exclude_id)
        result = await self.session.scalars(select(AppointmentModel).where(*conditions))
        return [self._to_domain(m) for m in result]

    async def search(self, filters: AppointmentFilters) -> tuple[list[Appointment], int]:
        conditions = []
        if filters.patient_id:
            conditions.append(AppointmentModel.patient_id == filters.patient_id)
        if filters.professional_id:
            conditions.append(AppointmentModel.professional_id == filters.professional_id)
        if filters.statuses:
            conditions.append(AppointmentModel.status.in_([s.value for s in filters.statuses]))
        if filters.date_from:
            conditions.append(AppointmentModel.start_time >= filters.date_from)
        if filters.date_to:
            conditions.append(AppointmentModel.start_time < filters.date_to)

        total = await self.session.scalar(select(func.count()).select_from(AppointmentModel).where(*conditions))
        order = AppointmentModel.start_time.desc() if filters.newest_first else AppointmentModel.start_time
        result = await self.session.scalars(
            select(AppointmentModel).where(*conditions).order_by(order)
            .limit(filters.limit).offset(filters.offset)
        )
        return [self._to_domain(m) for m in result], total

    async def get_patient_names(self, patient_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not patient_ids:
            return {}
        rows = await self.session.execute(
            select(PatientModel.id, PatientModel.full_name).where(PatientModel.id.in_(patient_ids)))
        return dict(rows.all())

    @staticmethod
    def _to_domain(m: AppointmentModel) -> Appointment:
        return Appointment(
            id=m.id, patient_id=m.patient_id, professional_id=m.professional_id,
            specialty_id=m.specialty_id, appointment_type=AppointmentType(m.appointment_type),
            status=AppointmentStatus(m.status), start_time=m.start_time,
            duration_minutes=m.duration_minutes, reason=m.reason, notes=m.notes,
            cancellation_reason=m.cancellation_reason, created_at=m.created_at, updated_at=m.updated_at,
            history=[StatusChange(
                id=h.id, from_status=AppointmentStatus(h.from_status) if h.from_status else None,
                to_status=AppointmentStatus(h.to_status), changed_at=h.changed_at, note=h.note,
            ) for h in m.history],
        )
