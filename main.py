from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

# Importação dos Routers
from app.presentation.api.v1.auth.router import router as auth_router
from app.presentation.api.v1.admin.user_router import router as user_router
from app.presentation.api.v1.admin.alert_router import router as alert_router
from app.presentation.api.v1.admin.patient_router import router as patient_router
from app.presentation.api.v1.pharmacy.pharmacy_router import router as pharmacy_router
from app.presentation.api.v1.billing.billing_router import router as billing_router
from app.presentation.api.v1.notifications.notification_router import router as notification_router

app = FastAPI(
    title="HealthOS - Sistema Integrado de Gestão Hospitalar",
    description="Plataforma de gestão de saúde com Arquitetura Limpa",
    version="1.0.0"
)

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de Rotas (Prefixos Únicos)
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Autenticação"])
app.include_router(user_router, prefix="/api/v1/admin/users", tags=["Administração de Usuários"])
app.include_router(patient_router, prefix="/api/v1/admin/patients", tags=["Gestão de Pacientes"])
app.include_router(alert_router, prefix="/api/v1/admin/alerts", tags=["Alertas Críticos"])
app.include_router(pharmacy_router, prefix="/api/v1/pharmacy", tags=["Farmácia"])
app.include_router(billing_router, prefix="/api/v1/billing", tags=["Faturamento"])
app.include_router(notification_router, prefix="/api/v1/notifications", tags=["Notificações"])

# Rota para servir o Portal Visual (Landing Page)
@app.get("/", response_class=FileResponse)
async def read_index():
    return "index.html"

# Rota para a documentação (opcional, o FastAPI já cria /docs, mas podemos criar um alias)
@app.get("/docs-link", include_in_schema=False)
async def docs_link():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
