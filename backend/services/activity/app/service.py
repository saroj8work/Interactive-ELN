from sqlalchemy.orm import Session

from eln_common.contracts import ActivityEventCreate

from .models import ActivityEvent
from .repository import ActivityRepository


class ActivityService:
    def __init__(self, repository: ActivityRepository, db: Session):
        self._repository = repository
        self._db = db

    def list_recent(self, organization_id: int, limit: int) -> list[ActivityEvent]:
        return self._repository.list_recent(organization_id, limit)

    def record_event(self, payload: ActivityEventCreate) -> ActivityEvent:
        event = ActivityEvent(**payload.model_dump())
        event = self._repository.add_if_new(event)
        self._db.commit()
        self._db.refresh(event)
        return event
