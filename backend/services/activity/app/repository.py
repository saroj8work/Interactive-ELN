from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import Session

from .models import ActivityEvent


class ActivityRepository:
    def __init__(self, db: Session):
        self._db = db

    def list_recent(self, organization_id: int, limit: int) -> list[ActivityEvent]:
        return list(
            self._db.scalars(
                select(ActivityEvent)
                .where(ActivityEvent.organization_id == organization_id)
                .order_by(ActivityEvent.occurred_at.desc(), ActivityEvent.id.desc())
                .limit(limit)
            )
        )

    def add_if_new(self, event: ActivityEvent) -> ActivityEvent:
        values = {
            "event_id": event.event_id,
            "source_service": event.source_service,
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "organization_id": event.organization_id,
            "occurred_at": event.occurred_at,
            "details": event.details,
        }
        dialect = self._db.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgres_insert(ActivityEvent).values(**values)
        else:
            existing = self._db.scalar(
                select(ActivityEvent).where(ActivityEvent.event_id == event.event_id)
            )
            if existing is not None:
                return existing
            self._db.add(event)
            self._db.flush()
            return event
        self._db.execute(
            statement.on_conflict_do_nothing(index_elements=["event_id"])
        )
        self._db.flush()
        saved_event = self._db.scalar(
            select(ActivityEvent).where(ActivityEvent.event_id == event.event_id)
        )
        if saved_event is None:
            raise RuntimeError("Activity event was not persisted.")
        return saved_event
