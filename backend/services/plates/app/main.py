import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from eln_common.config import required_postgresql_url
from eln_common.database import Database, Base
from eln_common.errors import register_domain_error_handlers

from . import models
from .router import create_router

# Use PLATES_DATABASE_URL if defined, otherwise fallback to NOTEBOOK_DATABASE_URL
db_url = os.getenv("PLATES_DATABASE_URL") or required_postgresql_url("NOTEBOOK_DATABASE_URL")
database = Database(db_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist
    _ = models
    Base.metadata.create_all(database.engine)
    try:
        yield
    finally:
        database.engine.dispose()


app = FastAPI(title="ELN Microplate & Assay Analysis Service", version="1.0.0", lifespan=lifespan)
register_domain_error_handlers(app)
app.include_router(create_router(database))


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "plates", "status": "ok"}

