from typing import List, Optional
import uuid
from datetime import datetime
from app.application.interfaces.triage_repository import TriageRepository
from app.domain.entities.triage import Triage, TriagePriority
from app.domain.exceptions.base import DomainException

class TriageUseCase:
    """
    Caso de Uso para a gestão de triagem de pacientes.
    Responsável por orquestrar a classificação de risco e a gestão da fila de espera.
    """

    def __init__(self, triage_repository: TriageRepository):
        self.triage_repository = triage_repository

    async def perform_triage(self,
                            patient_id: uuid.UUID,
                            nurse_id: uuid.UUID,
                            priority: TriagePriority,
                            main_complaint: str,
                            blood_pressure: str,
                            heart_rate: int,
                            temperature: float,
                            oxygen_saturation: int,
                            respiratory_rate: int,
                            observations: Optional[str] = None) -> Triage:
        """
        Realiza a triagem inicial do paciente.
        Se o paciente já tiver uma triagem ativa, ela é atualizada.
        """
        # 1. Verifica se já existe uma triagem para este paciente
        existing_triage = await self.triage_repository.get_latest_by_patient(patient_id)

        if existing_triage:
            # Atualiza a triagem existente (reclassificação)
            existing_triage.update_priority(priority)
            existing_triage.main_complaint = main_complaint
            existing_triage.blood_pressure = blood_pressure
            existing_triage.heart_rate = heart_rate
            existing_triage.temperature = temperature
            existing_triage.oxygen_saturation = oxygen_saturation
            existing_triage.respiratory_rate = respiratory_rate
            existing_triage.observations = observations
            existing_triage.triage_nurse_id = nurse_id

            return await self.triage_repository.update(existing_triage)

        # 2. Cria nova triagem
        triage = Triage(
            patient_id=patient_id,
            triage_nurse_id=nurse_id,
            priority=priority,
            main_complaint=main_complaint,
            blood_pressure=blood_pressure,
            heart_rate=heart_rate,
            temperature=temperature,
            oxygen_saturation=oxygen_saturation,
            respiratory_rate=respiratory_rate,
            observations=observations
        )

        return await self.triage_repository.save(triage)

    async def update_patient_priority(self, triage_id: uuid.UUID, new_priority: TriagePriority) -> Triage:
        """
        Reclassifica o paciente na fila com base em nova avaliação.
        """
        # Nota: Adicionaríamos um get_by_id no repositório para maior precisão
        # Por enquanto, simulamos a busca via paciente se necessário ou assumimos a existência.
        # Para este exemplo, vamos assumir a necessidade de expandir o repositório futuramente.
        raise NotImplementedError("Busca de triagem por ID requer atualização no TriageRepository")

    async def get_waiting_list_by_priority(self, priority: TriagePriority) -> List[Triage]:
        """
        Retorna todos os pacientes aguardando atendimento de uma determinada prioridade.
        """
        return await self.triage_repository.list_by_priority(priority.name)

    async def get_patient_triage_status(self, patient_id: uuid.UUID) -> Optional[Triage]:
        """
        Recupera o status atual de triagem de um paciente.
        """
        return await self.triage_repository.get_latest_by_patient(patient_id)
