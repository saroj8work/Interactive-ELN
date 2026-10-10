import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from eln_common.database import Database

from . import models
from .router import create_router

database = Database(os.getenv("DATABASE_URL", "sqlite:///./data/activity.db"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    _ = models
    database.create_schema()
    try:
        yield
    finally:
        database.engine.dispose()


app = FastAPI(title="ELN Activity Service", version="0.1.0", lifespan=lifespan)
app.include_router(create_router(database))


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "activity", "status": "ok"}
