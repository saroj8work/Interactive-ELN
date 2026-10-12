from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from eln_common.config import GatewaySettings
from eln_common.errors import register_domain_error_handlers
from services.identity.app.security import jwt_secret

from .client import ServiceClient
from .router import (
    activity_router,
    attachments_router,
    booking_router,
    inventory_router,
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
    try:
        yield
    finally:
        await app.state.service_client.close()


app = FastAPI(title="Interactive ELN API Gateway", version="0.1.0", lifespan=lifespan)
register_domain_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(projects_router)
app.include_router(notebook_router)
app.include_router(activity_router)
app.include_router(inventory_router)
app.include_router(templates_router)
app.include_router(attachments_router)
app.include_router(search_router)
app.include_router(booking_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
