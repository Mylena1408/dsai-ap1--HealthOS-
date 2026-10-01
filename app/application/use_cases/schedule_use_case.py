from typing import List, Optional
import uuid
from datetime import datetime
from app.application.interfaces.schedule_repository import ScheduleRepository
from app.domain.entities.schedule import Schedule, ScheduleStatus
from app.domain.exceptions.base import DomainException

class ScheduleUseCase:
    """
    Caso de Uso para a gestão de agendamentos.
    Orquestra a criação de slots de disponibilidade e a reserva de consultas,
    garantindo a integridade temporal e a ausência de conflitos.
    """

    def __init__(self, schedule_repository: ScheduleRepository):
        self.schedule_repository = schedule_repository

    async def create_availability_slot(self, doctor_id: uuid.UUID, start_time: datetime, end_time: datetime, notes: Optional[str] = None) -> Schedule:
        """
        Cria um novo slot de disponibilidade para um médico.
        Verifica se não há sobreposição com slots já existentes.
        """
        # 1. Verificação de conflitos (Overlap)
        overlaps = await self.schedule_repository.find_overlapping_slots(doctor_id, start_time, end_time)
        if overlaps:
            raise DomainException(
                message=f"O médico já possui agendamentos no intervalo solicitado. Slots conflitantes: {len(overlaps)}"
            )

        # 2. Criação da Entidade
        slot = Schedule(
            doctor_id=doctor_id,
            start_time=start_time,
            end_time=end_time,
            status=ScheduleStatus.AVAILABLE,
            notes=notes
        )

        # 3. Persistência
        return await self.schedule_repository.save(slot)

    async def book_appointment(self, schedule_id: uuid.UUID, patient_id: uuid.UUID) -> Schedule:
        """
        Reserva um slot disponível para um paciente específico.
        """
        slot = await self.schedule_repository.get_by_id(schedule_id)
        if not slot:
            raise DomainException(message="Slot de agendamento não encontrado.")

        if slot.status != ScheduleStatus.AVAILABLE:
            raise DomainException(message=f"Este horário não está disponível. Status atual: {slot.status.value}")

        # Executa a lógica de negócio da entidade
        slot.book(patient_id)

        # Persistência da alteração de estado
        return await self.schedule_repository.update(slot)

    async def cancel_appointment(self, schedule_id: uuid.UUID) -> Schedule:
        """
        Cancela um agendamento, liberando o slot ou marcando como cancelado.
        """
        slot = await self.schedule_repository.get_by_id(schedule_id)
        if not slot:
            raise DomainException(message="Slot de agendamento não encontrado.")

        slot.cancel()
        return await self.schedule_repository.update(slot)

    async def get_doctor_agenda(self, doctor_id: uuid.UUID, start: datetime, end: datetime) -> List[Schedule]:
        """
        Recupera a grade horária de um médico em um período.
        """
        return await self.schedule_repository.get_doctor_schedule(doctor_id, start, end)

    async def block_slot(self, schedule_id: uuid.UUID) -> Schedule:
        """
        Bloqueia um slot (ex: licença médica, imprevistos).
        """
        slot = await self.schedule_repository.get_by_id(schedule_id)
        if not slot:
            raise DomainException(message="Slot de agendamento não encontrado.")

        slot.block()
        return await self.schedule_repository.update(slot)

    async def get_my_appointments(self, patient_id: uuid.UUID) -> List[Schedule]:
        """
        Recupera todos os agendamentos confirmados de um paciente.
        """
        return await self.schedule_repository.get_patient_schedule(patient_id)
