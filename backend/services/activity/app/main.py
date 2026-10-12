from contextlib import asynccontextmanager

from fastapi import FastAPI

from eln_common.config import required_postgresql_url
from eln_common.database import Database

from . import models
from .router import create_router

database = Database(required_postgresql_url("ACTIVITY_DATABASE_URL"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    _ = models
    database.assert_schema_is_current("activity")
    try:
        yield
    finally:
        database.engine.dispose()


app = FastAPI(title="ELN Activity Service", version="0.1.0", lifespan=lifespan)
app.include_router(create_router(database))


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "activity", "status": "ok"}
