from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from eln_common.config import required_postgresql_url
from eln_common.database import Database
from eln_common.errors import register_domain_error_handlers

from . import models
from .router import create_router
from .security import jwt_secret

database = Database(required_postgresql_url("IDENTITY_DATABASE_URL"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    jwt_secret()
    _ = models
    database.assert_schema_is_current("identity")
    try:
        yield
    finally:
        database.engine.dispose()


app = FastAPI(title="Interactive ELN Identity Service", version="0.1.0", lifespan=lifespan)
register_domain_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-Bootstrap-Token", "X-Refresh-Token"],
)
app.include_router(create_router(database))


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "identity", "status": "ok"}
