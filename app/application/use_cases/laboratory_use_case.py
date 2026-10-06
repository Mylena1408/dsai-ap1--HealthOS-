from datetime import datetime, timedelta
from typing import Callable, Optional
import uuid

from app.application.dtos.clinical_monitoring_dto import (
    AnalyteDTO, AnalyteHistoryDTO, ExamRequestCreateDTO, ExamRequestDTO, ExamResultDTO, ExamStatusChangeDTO,
    ExamTypeDTO, LaboratoryDTO,
)
from app.application.dtos.common import Page
from app.application.interfaces.appointment_repository import AppointmentRepository
from app.application.interfaces.clinical_monitoring_repository import (
    ExamRequestFilters, ExamRequestNames, LaboratoryRepository,
)
from app.application.interfaces.medical_record_repository import PatientDirectoryRepository
from app.application.interfaces.professional_repository import ProfessionalRepository
from app.application.services.clinical_links import resolve_professional
from app.application.services.events import EventPublisher, NullPublisher
from app.domain.events import DomainEvent, EventType
from app.domain.entities.laboratory import ExamPriority, ExamRequest, ExamType
from app.domain.exceptions.common import BusinessRuleViolation, EntityNotFoundError


class LaboratoryUseCase:
    """Catálogo de exames e ciclo de vida das solicitações (resultados fictícios)."""

    def __init__(self, repo: LaboratoryRepository, directory: PatientDirectoryRepository,
                 professional_repo: ProfessionalRepository, appointment_repo: AppointmentRepository,
                 clock: Callable[[], datetime] = datetime.now, events: EventPublisher = NullPublisher()):
        self.repo = repo
        self.events = events
        self.directory = directory
        self.professional_repo = professional_repo
        self.appointment_repo = appointment_repo
        self.clock = clock

    # --------------------------------------------------------------- catálogo

    async def exam_types(self) -> list[ExamTypeDTO]:
        return [self._exam_type_dto(t) for t in await self.repo.list_exam_types()]

    async def laboratories(self) -> list[LaboratoryDTO]:
        return [LaboratoryDTO(id=lab.id, name=lab.name, address=lab.address)
                for lab in await self.repo.list_laboratories()]

    # ------------------------------------------------------------ solicitações

    async def request(self, dto: ExamRequestCreateDTO) -> ExamRequestDTO:
        if not await self.directory.get(dto.patient_id):
            raise EntityNotFoundError("Paciente", dto.patient_id)
        if not await self.repo.get_exam_type(dto.exam_type_id):
            raise EntityNotFoundError("Tipo de exame", dto.exam_type_id)
        if dto.laboratory_id and not await self.repo.get_laboratory(dto.laboratory_id):
            raise EntityNotFoundError("Laboratório", dto.laboratory_id)
        requested_by = await resolve_professional(self.appointment_repo, self.professional_repo,
                                                  dto.patient_id, dto.requested_by, dto.appointment_id)

        exam = ExamRequest(
            patient_id=dto.patient_id, exam_type_id=dto.exam_type_id, requested_at=self.clock(),
            requested_by=requested_by, appointment_id=dto.appointment_id, laboratory_id=dto.laboratory_id,
            priority=dto.priority, clinical_indication=dto.clinical_indication,
        )
        exam.register_creation()
        response = await self._respond(await self.repo.save_request(exam))
        await self._publish(EventType.EXAM_REQUESTED, response)
        return response

    async def schedule(self, request_id: uuid.UUID, scheduled_for: datetime) -> ExamRequestDTO:
        return await self._apply(request_id, lambda e, now: e.schedule(scheduled_for.replace(tzinfo=None), now))

    async def collect(self, request_id: uuid.UUID) -> ExamRequestDTO:
        return await self._apply(request_id, lambda e, now: e.collect(now), EventType.EXAM_COLLECTED)

    async def start_processing(self, request_id: uuid.UUID) -> ExamRequestDTO:
        return await self._apply(request_id, lambda e, now: e.start_processing(now))

    async def record_results(self, request_id: uuid.UUID, values: dict[str, float],
                             notes: Optional[str] = None) -> ExamRequestDTO:
        exam = await self._get(request_id)
        exam_type = await self.repo.get_exam_type(exam.exam_type_id)
        exam.record_results(exam_type, values, self.clock(), notes)
        response = await self._respond(await self.repo.save_request(exam))
        await self._publish(EventType.EXAM_RESULTED, response)
        return response

    async def validate(self, request_id: uuid.UUID, professional_id: uuid.UUID) -> ExamRequestDTO:
        professional = await self.professional_repo.get_by_id(professional_id)
        if not professional:
            raise EntityNotFoundError("Profissional", professional_id)
        if not professional.is_available_for_booking:
            raise BusinessRuleViolation("Somente profissionais ativos podem validar laudos.")
        return await self._apply(request_id, lambda e, now: e.validate(professional_id, now))

    async def return_for_correction(self, request_id: uuid.UUID, reason: str) -> ExamRequestDTO:
        return await self._apply(request_id, lambda e, now: e.return_for_correction(reason, now))

    async def release(self, request_id: uuid.UUID) -> ExamRequestDTO:
        return await self._apply(request_id, lambda e, now: e.release(now), EventType.EXAM_RELEASED)

    async def cancel(self, request_id: uuid.UUID, reason: str) -> ExamRequestDTO:
        return await self._apply(request_id, lambda e, now: e.cancel(reason, now), EventType.EXAM_CANCELLED)

    # ----------------------------------------------------------------- leitura

    async def get(self, request_id: uuid.UUID) -> ExamRequestDTO:
        return await self._respond(await self._get(request_id))

    async def search(self, filters: ExamRequestFilters) -> Page[ExamRequestDTO]:
        items, total = await self.repo.search_requests(filters)
        names = await self.repo.names_for(items)
        return Page(items=[self._to_dto(e, names) for e in items], total=total,
                    limit=filters.limit, offset=filters.offset)

    async def analyte_history(self, patient_id: uuid.UUID, analyte_code: str) -> AnalyteHistoryDTO:
        """Série temporal de um analito com resultados já liberados ao paciente."""
        if not await self.directory.get(patient_id):
            raise EntityNotFoundError("Paciente", patient_id)
        points = await self.repo.released_results(patient_id, analyte_code.upper())
        last = points[-1][1] if points else None
        return AnalyteHistoryDTO(
            analyte_code=analyte_code.upper(), analyte_name=last.analyte_name if last else None,
            unit=last.unit if last else None, reference_text=last.reference_text if last else None,
            points=[(moment, r.value, r.flag) for moment, r in points],
        )

    # ------------------------------------------------------------------ apoio

    async def _get(self, request_id: uuid.UUID) -> ExamRequest:
        exam = await self.repo.get_request(request_id)
        if not exam:
            raise EntityNotFoundError("Solicitação de exame", request_id)
        return exam

    async def _apply(self, request_id: uuid.UUID, action, event_type: Optional[EventType] = None) -> ExamRequestDTO:
        exam = await self._get(request_id)
        action(exam, self.clock())
        response = await self._respond(await self.repo.save_request(exam))
        if event_type:
            await self._publish(event_type, response)
        return response

    async def _publish(self, event_type: EventType, e: ExamRequestDTO) -> None:
        labels = {EventType.EXAM_REQUESTED: "Exame solicitado", EventType.EXAM_COLLECTED: "Amostra coletada",
                  EventType.EXAM_RESULTED: "Resultado registrado", EventType.EXAM_RELEASED: "Resultado liberado",
                  EventType.EXAM_CANCELLED: "Exame cancelado"}
        abnormal = [f"{r.analyte_name} {r.value:g} {r.unit}" for r in e.results if r.flag.is_abnormal]
        detail = f" Fora da referência: {'; '.join(abnormal)}." if event_type == EventType.EXAM_RELEASED and abnormal else ""
        await self.events.publish(DomainEvent(
            event_type=event_type, occurred_at=self.clock(), entity_type="Exame", entity_id=e.id,
            summary=f"{labels[event_type]}: {e.exam_name} — {e.patient_name}.{detail}",
            patient_id=e.patient_id, professional_id=e.requested_by,
            data={"exam_code": e.exam_code, "status": e.status.value, "sample_code": e.sample_code,
                  "urgent": e.priority == ExamPriority.URGENT, "abnormal": bool(abnormal)}))

    async def _respond(self, exam: ExamRequest) -> ExamRequestDTO:
        return self._to_dto(exam, await self.repo.names_for([exam]))

    @staticmethod
    def _exam_type_dto(t: ExamType) -> ExamTypeDTO:
        return ExamTypeDTO(
            id=t.id, code=t.code, name=t.name, category=t.category, sample_type=t.sample_type,
            turnaround_hours=t.turnaround_hours, preparation=t.preparation,
            analytes=[AnalyteDTO(code=a.code, name=a.name, unit=a.reference.unit, reference=a.reference.describe(),
                                 normal_min=a.reference.normal_min, normal_max=a.reference.normal_max,
                                 decimals=a.decimals) for a in t.analytes],
        )

    @staticmethod
    def _to_dto(e: ExamRequest, names: ExamRequestNames) -> ExamRequestDTO:
        exam_type = names.exam_types.get(e.exam_type_id)
        expected_by = (e.collected_at + timedelta(hours=exam_type.turnaround_hours)
                       if e.collected_at and exam_type else None)
        return ExamRequestDTO(
            id=e.id, patient_id=e.patient_id, patient_name=names.patients.get(e.patient_id),
            exam_type_id=e.exam_type_id, exam_code=exam_type.code if exam_type else None,
            exam_name=exam_type.name if exam_type else None,
            requested_by=e.requested_by, requested_by_name=names.professionals.get(e.requested_by),
            appointment_id=e.appointment_id, laboratory_id=e.laboratory_id,
            laboratory_name=names.laboratories.get(e.laboratory_id), priority=e.priority,
            clinical_indication=e.clinical_indication, status=e.status, allowed_transitions=e.allowed_transitions(),
            requested_at=e.requested_at, scheduled_for=e.scheduled_for, sample_code=e.sample_code,
            collected_at=e.collected_at, expected_by=expected_by,
            results=[ExamResultDTO(**vars(r)) for r in e.results],
            has_abnormal_results=e.has_abnormal_results, has_critical_results=e.has_critical_results,
            result_notes=e.result_notes, validated_by=e.validated_by,
            validated_by_name=names.professionals.get(e.validated_by), validated_at=e.validated_at,
            released_at=e.released_at, cancellation_reason=e.cancellation_reason,
            history=[ExamStatusChangeDTO(from_status=h.from_status, to_status=h.to_status,
                                         changed_at=h.changed_at, note=h.note) for h in e.history],
        )
