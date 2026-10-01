from typing import Optional, List
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.domain.entities.patient_alert import PatientAlert, AlertType, AlertSeverity
from app.application.interfaces.alert_repository import AlertRepository
from app.infrastructure.persistence.models.alert_model import PatientAlertModel

class SQLAlchemyAlertRepository(AlertRepository):
    """
    Implementação concreta do AlertRepository utilizando SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, alert: PatientAlert) -> PatientAlert:
        db_alert = PatientAlertModel(
            id=alert.id or uuid.uuid4(),
            patient_id=alert.patient_id,
            alert_type=alert.alert_type.value,
            severity=alert.severity.value,
            description=alert.description,
            is_active=alert.is_active
        )
        self.session.add(db_alert)
        await self.session.flush()
        alert.id = db_alert.id
        return alert

    async def get_active_alerts_by_patient(self, patient_id: uuid.UUID) -> List[PatientAlert]:
        stmt = select(PatientAlertModel).where(
            PatientAlertModel.patient_id == patient_id,
            PatientAlertModel.is_active == True
        )
        result = await self.session.execute(stmt)
        db_alerts = result.scalars().all()
        return [self._map_to_domain(a) for a in db_alerts]

    async def get_all_alerts_by_patient(self, patient_id: uuid.UUID) -> List[PatientAlert]:
        stmt = select(PatientAlertModel).where(PatientAlertModel.patient_id == patient_id)
        result = await self.session.execute(stmt)
        db_alerts = result.scalars().all()
        return [self._map_to_domain(a) for a in db_alerts]

    async def update(self, alert: PatientAlert) -> PatientAlert:
        db_alert = await self.session.get(PatientAlertModel, alert.id)
        if not db_alert:
            return None

        db_alert.description = alert.description
        db_alert.is_active = alert.is_active
        db_alert.alert_type = alert.alert_type.value
        db_alert.severity = alert.severity.value

        await self.session.flush()
        return alert

    def _map_to_domain(self, db_alert: PatientAlertModel) -> PatientAlert:
        return PatientAlert(
            id=db_alert.id,
            patient_id=db_alert.patient_id,
            alert_type=AlertType(db_alert.alert_type),
            severity=AlertSeverity(db_alert.severity),
            description=db_alert.description,
            is_active=db_alert.is_active,
            created_at=db_alert.created_at
        )
