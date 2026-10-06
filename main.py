from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
from datetime import datetime, time, timedelta
from sqlalchemy import select

# Importação dos Routers
from app.presentation.api.v1.auth.router import router as auth_router
from app.presentation.api.v1.admin.user_router import router as user_router
from app.presentation.api.v1.admin.alert_router import router as alert_router
from app.presentation.api.v1.admin.patient_router import router as patient_router
from app.presentation.api.v1.pharmacy.pharmacy_router import router as pharmacy_router
from app.presentation.api.v1.billing.billing_router import router as billing_router
from app.presentation.api.v1.notifications.notification_router import router as notification_router
from app.presentation.api.v1.clinical.router import router as clinical_router
from app.infrastructure.persistence.database import engine, AsyncSessionLocal
from app.infrastructure.persistence.models.user_model import Base
from app.infrastructure.persistence.models.user_model import UserModel
from app.infrastructure.persistence.models.schedule_model import ScheduleModel
from app.domain.entities.schedule import ScheduleStatus

# Registra todos os modelos no metadata antes de criar tabelas.
from app.infrastructure.persistence.models import (
    alert_model,
    audit_model,
    billing_model,
    clinical_model,
    medication_model,
    notification_model,
    patient_model,
    role_models,
    schedule_model,
    triage_model,
)

# CPF fictício com dígitos verificadores válidos, usado apenas na demonstração.
DEMO_DOCTOR_CPF = "11144477735"

app = FastAPI(
    title="HealthOS - Sistema Integrado de Gestão Hospitalar",
    description="Plataforma de gestão de saúde com Arquitetura Limpa",
    version="1.0.0"
)

@app.on_event("startup")
async def initialize_database():
    """Cria tabelas ausentes para permitir executar a demonstração localmente."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    # Inclui uma agenda ilustrativa para o portal não iniciar sem opções.
    async with AsyncSessionLocal() as session:
        doctor = await session.scalar(
            select(UserModel).where(UserModel.email == "medico.demo@healthos.local")
        )
        if doctor is None:
            doctor = UserModel(
                email="medico.demo@healthos.local",
                password_hash="demo-only",
                full_name="Médico da Demonstração",
                cpf=DEMO_DOCTOR_CPF,
                is_active=True,
            )
            session.add(doctor)
            await session.flush()
        elif doctor.cpf == "99999999999":
            # Bancos criados por versões anteriores usavam um CPF que a entidade
            # User rejeita, o que fazia a listagem de usuários falhar.
            doctor.cpf = DEMO_DOCTOR_CPF

        now = datetime.now().replace(second=0, microsecond=0)
        last_day = now + timedelta(days=14)
        existing_result = await session.execute(
            select(ScheduleModel.start_time).where(
                ScheduleModel.doctor_id == doctor.id,
                ScheduleModel.start_time >= now,
                ScheduleModel.start_time <= last_day,
            )
        )
        existing_starts = set(existing_result.scalars().all())

        for day_offset in range(14):
            day = (now + timedelta(days=day_offset)).date()
            if day.weekday() >= 5:
                continue
            for hour in (9, 10, 11, 14, 15, 16):
                start = datetime.combine(day, time(hour=hour))
                if start <= now or start in existing_starts:
                    continue
                session.add(ScheduleModel(
                    doctor_id=doctor.id,
                    start_time=start,
                    end_time=start + timedelta(minutes=30),
                    status=ScheduleStatus.AVAILABLE.value,
                    notes="Horário de demonstração",
                ))

        await session.commit()

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de Rotas (Prefixos Únicos)
app.include_router(auth_router, prefix="/api/v1", tags=["Autenticação"])
app.include_router(user_router, prefix="/api/v1/admin", tags=["Administração de Usuários"])
app.include_router(patient_router, prefix="/api/v1/admin/patients", tags=["Gestão de Pacientes"])
app.include_router(alert_router, prefix="/api/v1/admin", tags=["Alertas Críticos"])
app.include_router(pharmacy_router, prefix="/api/v1", tags=["Farmácia"])
app.include_router(billing_router, prefix="/api/v1", tags=["Faturamento"])
app.include_router(notification_router, prefix="/api/v1", tags=["Notificações"])
app.include_router(clinical_router, prefix="/api/v1", tags=["Serviços Clínicos"])

# Rota para servir o Portal Visual (Landing Page)
@app.get("/", response_class=FileResponse)
async def read_index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))

# Rota para a documentação (opcional, o FastAPI já cria /docs, mas podemos criar um alias)
@app.get("/docs-link", include_in_schema=False)
async def docs_link():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
