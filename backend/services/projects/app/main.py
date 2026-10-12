import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from eln_common.config import ServiceSettings
from eln_common.database import Base, Database
from eln_common.errors import register_domain_error_handlers
from eln_common.outbox import OutboxEvent, OutboxPublisher

from . import models
from .router import create_router

settings = ServiceSettings.for_service("projects")
database = Database(settings.database_url)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _ = models, OutboxEvent
    database.assert_schema_is_current("projects")
    publisher = OutboxPublisher(database, settings.activity_service_url)
    publisher_task = asyncio.create_task(publisher.run())
    try:
        yield
    finally:
        publisher.stop()
        await publisher_task
        database.engine.dispose()


app = FastAPI(title="ELN Projects Service", version="0.1.0", lifespan=lifespan)
register_domain_error_handlers(app)
app.include_router(create_router(database))


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "projects", "status": "ok"}
