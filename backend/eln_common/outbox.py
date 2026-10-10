import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import DateTime, Integer, JSON, String, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, Database

logger = logging.getLogger(__name__)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    source_service: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(48))
    entity_type: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[int] = mapped_column(Integer)
    organization_id: Mapped[int] = mapped_column(Integer, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)


def enqueue_event(
    db: Session,
    *,
    source_service: str,
    action: str,
    entity_type: str,
    entity_id: int,
    organization_id: int,
    details: dict[str, str],
) -> None:
    db.add(
        OutboxEvent(
            event_id=str(uuid4()),
            source_service=source_service,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            organization_id=organization_id,
            occurred_at=datetime.now(timezone.utc),
            details=details,
        )
    )


class OutboxPublisher:
    def __init__(
        self,
        database: Database,
        activity_service_url: str,
        *,
        poll_interval: float = 2,
    ):
        self._database = database
        self._activity_service_url = activity_service_url.rstrip("/")
        self._poll_interval = poll_interval
        self._stopping = asyncio.Event()

    async def run(self) -> None:
        async with httpx.AsyncClient(timeout=5) as client:
            while not self._stopping.is_set():
                await self._publish_batch(client)
                try:
                    await asyncio.wait_for(
                        self._stopping.wait(), timeout=self._poll_interval
                    )
                except TimeoutError:
                    continue

    def stop(self) -> None:
        self._stopping.set()

    async def _publish_batch(self, client: httpx.AsyncClient) -> None:
        try:
            with self._database.session() as db:
                events = list(
                    db.scalars(
                        select(OutboxEvent)
                        .where(OutboxEvent.published_at.is_(None))
                        .order_by(OutboxEvent.id)
                        .limit(25)
                    )
                )
                for event in events:
                    event.attempts += 1
                    try:
                        response = await client.post(
                            f"{self._activity_service_url}/internal/events",
                            json=self._payload(event),
                        )
                        response.raise_for_status()
                    except httpx.HTTPError:
                        logger.warning(
                            "Unable to publish outbox event %s; it will be retried.",
                            event.event_id,
                            exc_info=True,
                        )
                        continue
                    event.published_at = datetime.now(timezone.utc)
                db.commit()
        except SQLAlchemyError:
            logger.exception("Could not process an ELN service outbox batch.")

    @staticmethod
    def _payload(event: OutboxEvent) -> dict[str, Any]:
        return {
            "event_id": event.event_id,
            "source_service": event.source_service,
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "organization_id": event.organization_id,
            "occurred_at": event.occurred_at.isoformat(),
            "details": event.details,
        }
