"""Regras de vínculo entre registros clínicos, consultas e profissionais."""
from typing import Optional
import uuid

from app.application.interfaces.appointment_repository import AppointmentRepository
from app.application.interfaces.professional_repository import ProfessionalRepository
from app.domain.entities.appointment import AppointmentStatus
from app.domain.exceptions.common import BusinessRuleViolation, EntityNotFoundError


async def resolve_professional(appointment_repo: AppointmentRepository, professional_repo: ProfessionalRepository,
                               patient_id: uuid.UUID, professional_id: Optional[uuid.UUID],
                               appointment_id: Optional[uuid.UUID]) -> Optional[uuid.UUID]:
    """
    Valida o vínculo opcional com uma consulta (deve ser do paciente e ter ocorrido
    ou estar prevista) e devolve o profissional responsável: o informado ou, na
    falta dele, o da consulta.
    """
    if appointment_id:
        appointment = await appointment_repo.get_by_id(appointment_id)
        if not appointment or appointment.patient_id != patient_id:
            raise BusinessRuleViolation("A consulta informada não pertence a este paciente.")
        if appointment.status in (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW):
            raise BusinessRuleViolation("Não é possível vincular registros a uma consulta que não ocorreu.")
        professional_id = professional_id or appointment.professional_id
    if professional_id and not await professional_repo.get_by_id(professional_id):
        raise EntityNotFoundError("Profissional", professional_id)
    return professional_id
