from abc import ABC, abstractmethod
from typing import Optional, List
import uuid
from app.domain.entities.patient_alert import PatientAlert

class AlertRepository(ABC):
    """
    Interface de Repositório para Alertas de Pacientes.
    """

    @abstractmethod
    async def save(self, alert: PatientAlert) -> PatientAlert:
        """Persiste um alerta no banco de dados."""
        pass

    @abstractmethod
    async def get_active_alerts_by_patient(self, patient_id: uuid.UUID) -> List[PatientAlert]:
        """Recupera apenas os alertas ativos de um paciente."""
        pass

    @abstractmethod
    async def get_all_alerts_by_patient(self, patient_id: uuid.UUID) -> List[PatientAlert]:
        """Recupera todo o histórico de alertas de um paciente."""
        pass

    @abstractmethod
    async def update(self, alert: PatientAlert) -> PatientAlert:
        """Atualiza o status ou descrição de um alerta."""
        pass
