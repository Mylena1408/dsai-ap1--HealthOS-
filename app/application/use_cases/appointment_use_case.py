from datetime import datetime, timedelta
from typing import Callable, Optional
import uuid

from app.application.dtos.appointment_dto import (
    AppointmentCreateDTO, AppointmentResponseDTO, AvailableSlotDTO, StatusChangeDTO,
)
from app.application.dtos.common import Page
from app.application.interfaces.appointment_repository import AppointmentFilters, AppointmentRepository
from app.application.interfaces.patient_repository import PatientRepository
from app.application.interfaces.professional_repository import CatalogRepository, ProfessionalRepository
from app.application.services.events import EventPublisher, NullPublisher
from app.domain.events import DomainEvent, EventType
from app.domain.entities.appointment import ACTIVE_STATUSES, Appointment
from app.domain.entities.professional import Professional
from app.domain.exceptions.common import BusinessRuleViolation, ConflictError, EntityNotFoundError

DEFAULT_DURATION = 30
MAX_AVAILABILITY_DAYS = 31
EVENT_LABELS = {
    EventType.APPOINTMENT_BOOKED: "Consulta agendada", EventType.APPOINTMENT_RESCHEDULED: "Consulta remarcada",
    EventType.APPOINTMENT_CONFIRMED: "Consulta confirmada", EventType.APPOINTMENT_CANCELLED: "Consulta cancelada",
    EventType.APPOINTMENT_COMPLETED: "Consulta finalizada", EventType.APPOINTMENT_NO_SHOW: "Não comparecimento",
}


class AppointmentUseCase:
    """
    Orquestra o ciclo de vida das consultas. As regras de estado ficam na
    entidade Appointment; aqui ficam as regras que dependem de outros dados
    (existência do paciente, expediente do profissional e conflitos de agenda).
    """

    def __init__(self, appointment_repo: AppointmentRepository, professional_repo: ProfessionalRepository,
                 catalog_repo: CatalogRepository, patient_repo: PatientRepository,
                 clock: Callable[[], datetime] = datetime.now, events: EventPublisher = NullPublisher()):
        self.appointment_repo = appointment_repo
        self.events = events
        self.professional_repo = professional_repo
        self.catalog_repo = catalog_repo
        self.patient_repo = patient_repo
        self.clock = clock

    # ------------------------------------------------------------ agendamento

    async def book(self, dto: AppointmentCreateDTO) -> AppointmentResponseDTO:
        now = self.clock()
        if not await self.patient_repo.get_by_id(dto.patient_id):
            raise EntityNotFoundError("Paciente", dto.patient_id)
        professional = await self._get_professional(dto.professional_id)
        if not professional.is_available_for_booking:
            raise BusinessRuleViolation(f"O profissional está {professional.status.value} e não aceita agendamentos.")

        start = dto.start_time.replace(second=0, microsecond=0, tzinfo=None)
        if start <= now:
            raise BusinessRuleViolation("A consulta deve ser agendada para um horário futuro.")

        specialty_id = dto.specialty_id or professional.specialty_id
        duration = dto.duration_minutes or await self._default_duration(specialty_id)

        appointment = Appointment(
            patient_id=dto.patient_id, professional_id=professional.id, start_time=start,
            duration_minutes=duration, appointment_type=dto.appointment_type,
            specialty_id=specialty_id, reason=dto.reason, created_at=now,
        )
        await self._ensure_slot_is_free(appointment, professional)
        appointment.register_creation(now)
        response = await self._respond(await self.appointment_repo.save(appointment), now)
        await self._publish(EventType.APPOINTMENT_BOOKED, response, now)
        return response

    async def reschedule(self, appointment_id: uuid.UUID, new_start: datetime,
                         duration_minutes: Optional[int] = None) -> AppointmentResponseDTO:
        now = self.clock()
        appointment = await self._get(appointment_id)
        professional = await self._get_professional(appointment.professional_id)
        appointment.reschedule(new_start.replace(second=0, microsecond=0, tzinfo=None), now, duration_minutes)
        await self._ensure_slot_is_free(appointment, professional)
        response = await self._respond(await self.appointment_repo.save(appointment), now)
        await self._publish(EventType.APPOINTMENT_RESCHEDULED, response, now)
        return response

    # ------------------------------------------------------------ transições

    async def confirm(self, appointment_id: uuid.UUID) -> AppointmentResponseDTO:
        return await self._apply(appointment_id, lambda a, now: a.confirm(now), EventType.APPOINTMENT_CONFIRMED)

    async def start(self, appointment_id: uuid.UUID) -> AppointmentResponseDTO:
        return await self._apply(appointment_id, lambda a, now: a.start(now))

    async def complete(self, appointment_id: uuid.UUID, notes: Optional[str] = None) -> AppointmentResponseDTO:
        return await self._apply(appointment_id, lambda a, now: a.complete(now, notes),
                                 EventType.APPOINTMENT_COMPLETED)

    async def cancel(self, appointment_id: uuid.UUID, reason: str) -> AppointmentResponseDTO:
        return await self._apply(appointment_id, lambda a, now: a.cancel(now, reason),
                                 EventType.APPOINTMENT_CANCELLED)

    async def mark_no_show(self, appointment_id: uuid.UUID) -> AppointmentResponseDTO:
        return await self._apply(appointment_id, lambda a, now: a.mark_no_show(now), EventType.APPOINTMENT_NO_SHOW)

    # ---------------------------------------------------------------- leitura

    async def get(self, appointment_id: uuid.UUID) -> AppointmentResponseDTO:
        return await self._respond(await self._get(appointment_id), self.clock())

    async def search(self, filters: AppointmentFilters) -> Page[AppointmentResponseDTO]:
        now = self.clock()
        items, total = await self.appointment_repo.search(filters)
        patient_names = await self.appointment_repo.get_patient_names({a.patient_id for a in items})
        professional_names = await self.professional_repo.get_names({a.professional_id for a in items})
        return Page(
            items=[self._to_dto(a, now, patient_names, professional_names) for a in items],
            total=total, limit=filters.limit, offset=filters.offset,
        )

    async def available_slots(self, professional_id: uuid.UUID, date_from: datetime, days: int = 7,
                              duration_minutes: Optional[int] = None) -> list[AvailableSlotDTO]:
        """Horários livres = janelas do expediente − consultas ativas − horários passados."""
        if not 1 <= days <= MAX_AVAILABILITY_DAYS:
            raise BusinessRuleViolation(f"O período deve ter entre 1 e {MAX_AVAILABILITY_DAYS} dias.")
        professional = await self._get_professional(professional_id)
        if not professional.is_available_for_booking:
            return []
        duration = duration_minutes or await self._default_duration(professional.specialty_id)
        step = timedelta(minutes=duration)

        first_day = date_from.date()
        range_start = datetime.combine(first_day, datetime.min.time())
        range_end = range_start + timedelta(days=days)
        # date_from recua 12h para incluir consultas que começam antes e terminam no período.
        busy, _ = await self.appointment_repo.search(AppointmentFilters(
            professional_id=professional_id, statuses=list(ACTIVE_STATUSES),
            date_from=range_start - timedelta(hours=12), date_to=range_end, limit=10_000,
        ))

        now = self.clock()
        slots = []
        for offset in range(days):
            day = first_day + timedelta(days=offset)
            for window in (w for w in professional.working_hours if w.weekday == day.weekday()):
                cursor = datetime.combine(day, window.start_time)
                window_end = datetime.combine(day, window.end_time)
                while cursor + step <= window_end:
                    end = cursor + step
                    if cursor > now and not any(a.overlaps(cursor, end) for a in busy):
                        slots.append(AvailableSlotDTO(start_time=cursor, end_time=end))
                    cursor = end
        return slots

    # ------------------------------------------------------------------ apoio

    async def _apply(self, appointment_id: uuid.UUID, action,
                     event_type: Optional[EventType] = None) -> AppointmentResponseDTO:
        now = self.clock()
        appointment = await self._get(appointment_id)
        action(appointment, now)
        response = await self._respond(await self.appointment_repo.save(appointment), now)
        if event_type:
            await self._publish(event_type, response, now)
        return response

    async def _publish(self, event_type: EventType, a: AppointmentResponseDTO, now: datetime) -> None:
        await self.events.publish(DomainEvent(
            event_type=event_type, occurred_at=now, entity_type="Consulta", entity_id=a.id,
            summary=f"{EVENT_LABELS[event_type]}: {a.patient_name} com {a.professional_name} "
                    f"em {a.start_time:%d/%m/%Y %H:%M}.",
            patient_id=a.patient_id, professional_id=a.professional_id,
            data={"status": a.status.value, "start_time": a.start_time,
                  "reason": a.cancellation_reason}))

    async def _ensure_slot_is_free(self, appointment: Appointment, professional: Professional) -> None:
        start, end = appointment.start_time, appointment.end_time
        if professional.working_hours and not professional.works_during(start, end):
            raise BusinessRuleViolation("O horário está fora do expediente do profissional.")

        conflicts = await self.appointment_repo.find_active_overlapping(
            start, end, professional_id=professional.id, exclude_id=appointment.id)
        if conflicts:
            raise ConflictError("O profissional já possui consulta nesse horário.")
        conflicts = await self.appointment_repo.find_active_overlapping(
            start, end, patient_id=appointment.patient_id, exclude_id=appointment.id)
        if conflicts:
            raise ConflictError("O paciente já possui outra consulta nesse horário.")

    async def _default_duration(self, specialty_id: Optional[uuid.UUID]) -> int:
        if specialty_id:
            specialty = await self.catalog_repo.get_specialty(specialty_id)
            if specialty:
                return specialty.default_duration_minutes
        return DEFAULT_DURATION

    async def _get(self, appointment_id: uuid.UUID) -> Appointment:
        appointment = await self.appointment_repo.get_by_id(appointment_id)
        if not appointment:
            raise EntityNotFoundError("Consulta", appointment_id)
        return appointment

    async def _get_professional(self, professional_id: uuid.UUID) -> Professional:
        professional = await self.professional_repo.get_by_id(professional_id)
        if not professional:
            raise EntityNotFoundError("Profissional", professional_id)
        return professional

    async def _respond(self, appointment: Appointment, now: datetime) -> AppointmentResponseDTO:
        patient_names = await self.appointment_repo.get_patient_names({appointment.patient_id})
        professional_names = await self.professional_repo.get_names({appointment.professional_id})
        return self._to_dto(appointment, now, patient_names, professional_names)

    @staticmethod
    def _to_dto(a: Appointment, now: datetime, patient_names: dict, professional_names: dict) -> AppointmentResponseDTO:
        return AppointmentResponseDTO(
            id=a.id, patient_id=a.patient_id, patient_name=patient_names.get(a.patient_id),
            professional_id=a.professional_id, professional_name=professional_names.get(a.professional_id),
            specialty_id=a.specialty_id, appointment_type=a.appointment_type, status=a.status,
            start_time=a.start_time, end_time=a.end_time, duration_minutes=a.duration_minutes,
            reason=a.reason, notes=a.notes, cancellation_reason=a.cancellation_reason,
            allowed_transitions=a.allowed_transitions(now),
            history=[StatusChangeDTO(from_status=h.from_status, to_status=h.to_status,
                                     changed_at=h.changed_at, note=h.note) for h in a.history],
        )
