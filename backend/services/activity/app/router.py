from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from eln_common.contracts import (
    ActivityEventCreate,
    ActivityEventRead,
    NotificationRead,
    WebhookDeliveryRead,
    WebhookEndpointCreate,
    WebhookEndpointCreated,
    WebhookEndpointRead,
    WebhookEndpointUpdate,
)
from eln_common.database import Database

from .repository import ActivityRepository
from .service import ActivityService


def create_router(database: Database) -> APIRouter:
    router = APIRouter(tags=["activity"])

    def get_service(db: Annotated[Session, Depends(database.dependency)]) -> ActivityService:
        return ActivityService(ActivityRepository(db), db)

    def endpoint_read(endpoint) -> WebhookEndpointRead:
        return WebhookEndpointRead(
            id=endpoint.id,
            name=endpoint.name,
            url=endpoint.url,
            event_types=endpoint.event_types,
            secret_prefix=endpoint.secret_prefix,
            enabled=endpoint.enabled,
            created_at=endpoint.created_at,
            revoked_at=endpoint.revoked_at,
        )

    @router.get("/activity", response_model=list[ActivityEventRead])
    def list_activity(
        service: Annotated[ActivityService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> list[ActivityEventRead]:
        return service.list_recent(organization_id, limit)

    @router.get("/notifications", response_model=list[NotificationRead])
    def list_notifications(
        service: Annotated[ActivityService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        user_id: Annotated[int, Header(alias="X-User-ID")],
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> list[NotificationRead]:
        return service.list_notifications(organization_id, user_id, limit)

    @router.post(
        "/notifications/{notification_id}/read",
        response_model=NotificationRead,
    )
    def mark_notification_read(
        notification_id: int,
        service: Annotated[ActivityService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        user_id: Annotated[int, Header(alias="X-User-ID")],
    ) -> NotificationRead:
        return service.mark_notification_read(
            organization_id, user_id, notification_id
        )

    @router.get(
        "/activity/samples/{sample_id}/history",
        response_model=list[ActivityEventRead],
    )
    def list_sample_location_history(
        sample_id: int,
        service: Annotated[ActivityService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> list[ActivityEventRead]:
        return service.list_sample_location_history(
            organization_id, sample_id, limit
        )

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

    @router.get("/integrations/webhooks", response_model=list[WebhookEndpointRead])
    def list_webhook_endpoints(
        service: Annotated[ActivityService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        organization_role: Annotated[str, Header(alias="X-Organization-Role")],
    ) -> list[WebhookEndpointRead]:
        if organization_role != "admin":
            raise HTTPException(status_code=403, detail="Organization admin role required.")
        return [endpoint_read(item) for item in service.list_webhook_endpoints(organization_id)]

    @router.post(
        "/integrations/webhooks",
        response_model=WebhookEndpointCreated,
        status_code=status.HTTP_201_CREATED,
    )
    def create_webhook_endpoint(
        payload: WebhookEndpointCreate,
        service: Annotated[ActivityService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        user_id: Annotated[int, Header(alias="X-User-ID")],
        organization_role: Annotated[str, Header(alias="X-Organization-Role")],
    ) -> WebhookEndpointCreated:
        if organization_role != "admin":
            raise HTTPException(status_code=403, detail="Organization admin role required.")
        endpoint, secret = service.create_webhook_endpoint(organization_id, user_id, payload)
        return WebhookEndpointCreated(**endpoint_read(endpoint).model_dump(), secret=secret)

    @router.patch("/integrations/webhooks/{endpoint_id}", response_model=WebhookEndpointRead)
    def update_webhook_endpoint(
        endpoint_id: int,
        payload: WebhookEndpointUpdate,
        service: Annotated[ActivityService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        organization_role: Annotated[str, Header(alias="X-Organization-Role")],
    ) -> WebhookEndpointRead:
        if organization_role != "admin":
            raise HTTPException(status_code=403, detail="Organization admin role required.")
        endpoint = service.update_webhook_endpoint(
            organization_id, endpoint_id, payload.model_dump(exclude_unset=True)
        )
        return endpoint_read(endpoint)

    @router.post("/integrations/webhooks/{endpoint_id}/rotate-secret", response_model=WebhookEndpointCreated)
    def rotate_webhook_secret(
        endpoint_id: int,
        service: Annotated[ActivityService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        organization_role: Annotated[str, Header(alias="X-Organization-Role")],
    ) -> WebhookEndpointCreated:
        if organization_role != "admin":
            raise HTTPException(status_code=403, detail="Organization admin role required.")
        endpoint, secret = service.rotate_webhook_secret(organization_id, endpoint_id)
        return WebhookEndpointCreated(**endpoint_read(endpoint).model_dump(), secret=secret)

    @router.get(
        "/integrations/webhooks/{endpoint_id}/deliveries",
        response_model=list[WebhookDeliveryRead],
    )
    def list_webhook_deliveries(
        endpoint_id: int,
        service: Annotated[ActivityService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        organization_role: Annotated[str, Header(alias="X-Organization-Role")],
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> list[WebhookDeliveryRead]:
        if organization_role != "admin":
            raise HTTPException(status_code=403, detail="Organization admin role required.")
        return [WebhookDeliveryRead.model_validate(item) for item in service.list_webhook_deliveries(
            organization_id, endpoint_id, limit
        )]

    @router.delete("/integrations/webhooks/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
    def revoke_webhook_endpoint(
        endpoint_id: int,
        service: Annotated[ActivityService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        organization_role: Annotated[str, Header(alias="X-Organization-Role")],
    ) -> Response:
        if organization_role != "admin":
            raise HTTPException(status_code=403, detail="Organization admin role required.")
        service.revoke_webhook_endpoint(organization_id, endpoint_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
