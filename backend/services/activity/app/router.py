from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from eln_common.contracts import ActivityEventCreate, ActivityEventRead
from eln_common.database import Database

from .repository import ActivityRepository
from .service import ActivityService


def create_router(database: Database) -> APIRouter:
    router = APIRouter(tags=["activity"])

    def get_service(db: Annotated[Session, Depends(database.dependency)]) -> ActivityService:
        return ActivityService(ActivityRepository(db), db)

    @router.get("/activity", response_model=list[ActivityEventRead])
    def list_activity(
        service: Annotated[ActivityService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> list[ActivityEventRead]:
        return service.list_recent(organization_id, limit)

    @router.post(
        "/internal/events",
        response_model=ActivityEventRead,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def record_event(
        payload: ActivityEventCreate,
        service: Annotated[ActivityService, Depends(get_service)],
    ) -> ActivityEventRead:
        return service.record_event(payload)

    return router
