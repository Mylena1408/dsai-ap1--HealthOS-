"""Endpoints de observabilidade: /health, /status e /metrics."""
import platform
import time

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.observability.metrics import metrics
from app.infrastructure.persistence.database import engine, get_db
from app.infrastructure.persistence.models.appointment_model import AppointmentModel
from app.infrastructure.persistence.models.billing_model import InvoiceModel
from app.infrastructure.persistence.models.medication_model import MedicationModel
from app.infrastructure.persistence.models.patient_model import PatientModel
from app.infrastructure.persistence.models.professional_model import ProfessionalModel
from app.infrastructure.persistence.models.schedule_model import ScheduleModel
from app.infrastructure.persistence.models.user_model import UserModel

APP_VERSION = "1.6.0"

router = APIRouter(tags=["Sistema"])

# Volume de dados exibido em /status (apenas contagens, nenhum dado pessoal).
_COUNTED_MODELS = {
    "patients": PatientModel,
    "users": UserModel,
    "professionals": ProfessionalModel,
    "appointments": AppointmentModel,
    "schedules": ScheduleModel,
    "medications": MedicationModel,
    "invoices": InvoiceModel,
}


@router.get("/health", summary="Liveness: o processo está respondendo")
async def health():
    return {"status": "ok"}


@router.get("/status", summary="Estado da aplicação e do banco de dados")
async def app_status(response: Response, session: AsyncSession = Depends(get_db)):
    database = {"dialect": engine.dialect.name}
    try:
        started = time.perf_counter()
        await session.execute(text("SELECT 1"))
        database["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        database["status"] = "ok"
        database["records"] = {
            name: await session.scalar(select(func.count()).select_from(model))
            for name, model in _COUNTED_MODELS.items()
        }
    except Exception as exc:  # o objetivo do endpoint é reportar a falha, não propagá-la
        database["status"] = "error"
        database["error"] = exc.__class__.__name__
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if database["status"] == "ok" else "degraded",
        "version": APP_VERSION,
        "python": platform.python_version(),
        "uptime_seconds": round(metrics.uptime_seconds(), 1),
        "database": database,
    }


@router.get("/metrics", summary="Métricas de requisições desde o último reinício")
async def get_metrics():
    return metrics.snapshot()
