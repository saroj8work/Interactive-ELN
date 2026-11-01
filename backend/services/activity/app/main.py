from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI

from eln_common.config import required_postgresql_url
from eln_common.database import Database
from eln_common.errors import register_domain_error_handlers

from . import models
from .router import create_router
from .webhooks import WebhookDeliveryWorker

database = Database(required_postgresql_url("ACTIVITY_DATABASE_URL"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = models
    database.assert_schema_is_current("activity")
    worker = WebhookDeliveryWorker(database)
    worker_task = asyncio.create_task(worker.run())
    app.state.webhook_worker = worker
    try:
        yield
    finally:
        worker.stop()
        await worker_task
        database.engine.dispose()


app = FastAPI(title="ELN Activity Service", version="0.1.0", lifespan=lifespan)
register_domain_error_handlers(app)
app.include_router(create_router(database))


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "activity", "status": "ok"}
