from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from eln_common.config import GatewaySettings
from eln_common.errors import register_domain_error_handlers
from services.identity.app.security import jwt_secret

from .client import ServiceClient
from .router import (
    activity_router,
    attachments_router,
    aura_router,
    booking_router,
    inventory_router,
    integrations_router,
    notebook_router,
    projects_router,
    search_router,
    templates_router,
)

settings = GatewaySettings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    jwt_secret()
    app.state.service_client = ServiceClient(settings)
    app.state.identity_client = httpx.AsyncClient(timeout=5)
    try:
        yield
    finally:
        await app.state.service_client.close()
        await app.state.identity_client.aclose()


app = FastAPI(title="Interactive ELN API Gateway", version="0.1.0", lifespan=lifespan)
app.state.settings = settings
register_domain_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
from .plates_router import plates_router
from .cheminformatics_router import cheminformatics_router
from .molecular_router import molecular_router
from .canvas_router import canvas_router
from .analytics_router import analytics_router
from .dossier_router import dossier_router
from .thermal_printer_router import thermal_printer_router

app.include_router(projects_router)
app.include_router(notebook_router)
app.include_router(activity_router)
app.include_router(inventory_router)
app.include_router(templates_router)
app.include_router(attachments_router)
app.include_router(search_router)
app.include_router(booking_router)
app.include_router(integrations_router)
app.include_router(aura_router)
app.include_router(plates_router)
app.include_router(cheminformatics_router)
app.include_router(molecular_router)
app.include_router(canvas_router)
app.include_router(analytics_router)
app.include_router(dossier_router)
app.include_router(thermal_printer_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
