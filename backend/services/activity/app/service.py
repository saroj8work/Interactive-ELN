import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from eln_common.contracts import ActivityEventCreate, WebhookEndpointCreate
from eln_common.errors import EntityNotFoundError, InvalidInputError

from .models import ActivityEvent, Notification, WebhookDelivery, WebhookEndpoint
from .repository import ActivityRepository
from .webhooks import encrypt_secret, validate_webhook_destination


class ActivityService:
    def __init__(self, repository: ActivityRepository, db: Session):
        self._repository = repository
        self._db = db

    def list_recent(self, organization_id: int, limit: int) -> list[ActivityEvent]:
        return self._repository.list_recent(organization_id, limit)

    def list_sample_location_history(
        self, organization_id: int, sample_id: int, limit: int = 100
    ) -> list[ActivityEvent]:
        return self._repository.list_sample_location_history(
            organization_id, sample_id, limit
        )

    def record_event(self, payload: ActivityEventCreate) -> ActivityEvent:
        existing = self._db.scalar(
            select(ActivityEvent).where(ActivityEvent.event_id == payload.event_id)
        )
        if existing is not None:
            return existing
        event = ActivityEvent(**payload.model_dump())
        event = self._repository.add_if_new(event)
        self._create_approval_notifications(event)
        self._create_sample_custody_notification(event)
        event_type = f"{event.source_service}.{event.action}"
        endpoints = self._db.scalars(
            select(WebhookEndpoint).where(
                WebhookEndpoint.organization_id == event.organization_id,
                WebhookEndpoint.enabled.is_(True),
                WebhookEndpoint.revoked_at.is_(None),
            )
        )
        event_payload = {
            "event_id": event.event_id,
            "source_service": event.source_service,
            "action": event.action,
            "event_type": event_type,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "organization_id": event.organization_id,
            "occurred_at": event.occurred_at.isoformat(),
            "details": event.details,
        }
        for endpoint in endpoints:
            if "*" in endpoint.event_types or event_type in endpoint.event_types:
                self._db.add(WebhookDelivery(
                    organization_id=event.organization_id,
                    endpoint_id=endpoint.id,
                    event_id=event.event_id,
                    event_type=event_type,
                    payload=event_payload,
                    attempts=0,
                    next_attempt_at=datetime.now(timezone.utc),
                    created_at=datetime.now(timezone.utc),
                ))
        self._db.commit()
        self._db.refresh(event)
        return event

    def list_notifications(
        self, organization_id: int, user_id: int, limit: int = 50
    ) -> list[Notification]:
        return list(self._db.scalars(
            select(Notification)
            .where(
                Notification.organization_id == organization_id,
                Notification.user_id == user_id,
            )
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit)
        ))

    def mark_notification_read(
        self, organization_id: int, user_id: int, notification_id: int
    ) -> Notification:
        notification = self._db.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.organization_id == organization_id,
                Notification.user_id == user_id,
            )
        )
        if notification is None:
            raise EntityNotFoundError("Notification not found.")
        if notification.read_at is None:
            notification.read_at = datetime.now(timezone.utc)
            self._db.commit()
            self._db.refresh(notification)
        return notification

    def _create_approval_notifications(self, event: ActivityEvent) -> None:
        details = event.details
        action = event.action
        name = details.get("experiment_name", "Experiment")
        project_id = details.get("project_id", "")
        experiment_id = details.get("experiment_id", "")
        approval_id = details.get("approval_id", str(event.entity_id))
        review_mode = details.get("review_mode", "sequential")
        recipients: list[int] = []
        if action == "experiment_approval_requested":
            reviewer_ids = details.get("reviewer_user_ids", "").split(",")
            if review_mode == "parallel":
                recipients = [int(reviewer_id) for reviewer_id in reviewer_ids if reviewer_id.isdigit()]
            elif reviewer_ids and reviewer_ids[0].isdigit():
                recipients = [int(reviewer_ids[0])]
            title = f"Approval requested: {name}"
            message = (
                "Review this experiment; all assigned reviewers must approve."
                if review_mode == "parallel"
                else "Review this experiment to start its approval sequence."
            )
        elif action == "experiment_approval_step_approved":
            if review_mode == "parallel":
                return
            next_reviewer = details.get("next_reviewer_user_id", "")
            if next_reviewer.isdigit():
                recipients = [int(next_reviewer)]
            title = f"Approval needed: {name}"
            message = "The previous review step passed. Your review is now required."
        elif action == "experiment_approval_branch_started":
            reviewer_ids = details.get("reviewer_user_ids", "").split(",")
            if reviewer_ids and reviewer_ids[0].isdigit():
                recipients = [int(reviewer_ids[0])]
            title = f"Rejection review needed: {name}"
            message = "A reviewer rejected the main path. Your review is now required."
        elif action in {
            "experiment_approval_approved",
            "experiment_approval_rejected",
            "experiment_approval_stale",
        }:
            requester = details.get("requested_by_user_id", "")
            if requester.isdigit():
                recipients = [int(requester)]
            state = action.rsplit("_", 1)[-1]
            title = f"Approval {state}: {name}"
            message = details.get("status", state).capitalize()
        else:
            return
        for recipient_id in set(recipients):
            if recipient_id <= 0:
                continue
            existing = self._db.scalar(
                select(Notification.id).where(
                    Notification.organization_id == event.organization_id,
                    Notification.user_id == recipient_id,
                    Notification.event_id == event.event_id,
                )
            )
            if existing is not None:
                continue
            self._db.add(Notification(
                organization_id=event.organization_id,
                user_id=recipient_id,
                event_id=event.event_id,
                title=title[:200],
                message=message[:500],
                entity_type="experiment",
                entity_id=int(experiment_id) if experiment_id.isdigit() else event.entity_id,
                details={
                    "project_id": project_id,
                    "experiment_id": experiment_id,
                    "approval_id": approval_id,
                    "action": action,
                },
                created_at=event.occurred_at,
            ))

    def _create_sample_custody_notification(self, event: ActivityEvent) -> None:
        if event.entity_type != "sample":
            return
        details = event.details
        if event.action == "custody_transfer_requested":
            recipient_key = "to_user_id"
            title = f"Sample transfer requested: {details.get('sample_name', 'Sample')}"
            message = "Confirm receipt to become this sample's recorded custodian."
        elif event.action == "custody_transfer_accepted":
            recipient_key = "from_user_id"
            title = f"Sample transfer accepted: {details.get('sample_name', 'Sample')}"
            message = "The recipient confirmed receipt; custody has been updated."
        elif event.action == "custody_transfer_cancelled":
            recipient_key = "to_user_id"
            title = f"Sample transfer cancelled: {details.get('sample_name', 'Sample')}"
            message = (
                "The sample was archived, so the pending transfer was cancelled."
                if details.get("reason") == "sample_archived"
                else "The sender cancelled the pending transfer."
            )
        else:
            return
        recipient = details.get(recipient_key, "")
        if not recipient.isdigit() or int(recipient) <= 0:
            return
        existing = self._db.scalar(select(Notification.id).where(
            Notification.organization_id == event.organization_id,
            Notification.user_id == int(recipient),
            Notification.event_id == event.event_id,
        ))
        if existing is not None:
            return
        self._db.add(Notification(
            organization_id=event.organization_id,
            user_id=int(recipient),
            event_id=event.event_id,
            title=title[:200],
            message=message,
            entity_type="sample",
            entity_id=event.entity_id,
            details={"action": event.action, "transfer_id": details.get("transfer_id", "")},
            created_at=event.occurred_at,
        ))

    def list_webhook_endpoints(self, organization_id: int) -> list[WebhookEndpoint]:
        return list(self._db.scalars(
            select(WebhookEndpoint)
            .where(WebhookEndpoint.organization_id == organization_id)
            .order_by(WebhookEndpoint.created_at.desc(), WebhookEndpoint.id.desc())
        ))

    def create_webhook_endpoint(
        self, organization_id: int, user_id: int, values: WebhookEndpointCreate
    ) -> tuple[WebhookEndpoint, str]:
        name = values.name.strip()
        if not name:
            raise InvalidInputError("Integration name cannot be blank.")
        validate_webhook_destination(values.url)
        secret = f"whsec_{secrets.token_urlsafe(36)}"
        endpoint = WebhookEndpoint(
            organization_id=organization_id,
            created_by_user_id=user_id,
            name=name,
            url=values.url,
            event_types=values.event_types,
            secret_prefix=secret[:24],
            encrypted_secret=encrypt_secret(secret),
            enabled=True,
            created_at=datetime.now(timezone.utc),
            revoked_at=None,
        )
        self._db.add(endpoint)
        self._db.commit()
        self._db.refresh(endpoint)
        return endpoint, secret

    def update_webhook_endpoint(
        self, organization_id: int, endpoint_id: int, values: dict
    ) -> WebhookEndpoint:
        endpoint = self._get_webhook_endpoint(organization_id, endpoint_id)
        if endpoint.revoked_at is not None:
            raise InvalidInputError("Revoked integrations cannot be edited.")
        if not values:
            raise InvalidInputError("Provide at least one integration field to update.")
        if any(value is None for value in values.values()):
            raise InvalidInputError("Integration fields cannot be null.")
        if "name" in values:
            values["name"] = values["name"].strip()
            if not values["name"]:
                raise InvalidInputError("Integration name cannot be blank.")
        if "url" in values:
            validate_webhook_destination(values["url"])
        for field, value in values.items():
            setattr(endpoint, field, value)
        self._db.commit()
        self._db.refresh(endpoint)
        return endpoint

    def rotate_webhook_secret(
        self, organization_id: int, endpoint_id: int
    ) -> tuple[WebhookEndpoint, str]:
        endpoint = self._get_webhook_endpoint(organization_id, endpoint_id)
        if endpoint.revoked_at is not None:
            raise InvalidInputError("Revoked integrations cannot rotate their secret.")
        secret = f"whsec_{secrets.token_urlsafe(36)}"
        endpoint.secret_prefix = secret[:24]
        endpoint.encrypted_secret = encrypt_secret(secret)
        self._db.commit()
        self._db.refresh(endpoint)
        return endpoint, secret

    def revoke_webhook_endpoint(self, organization_id: int, endpoint_id: int) -> None:
        endpoint = self._get_webhook_endpoint(organization_id, endpoint_id)
        if endpoint.revoked_at is not None:
            return
        now = datetime.now(timezone.utc)
        endpoint.enabled = False
        endpoint.revoked_at = now
        pending = self._db.scalars(select(WebhookDelivery).where(
            WebhookDelivery.endpoint_id == endpoint_id,
            WebhookDelivery.delivered_at.is_(None),
            WebhookDelivery.failed_at.is_(None),
        ))
        for delivery in pending:
            delivery.failed_at = now
            delivery.next_attempt_at = None
            delivery.last_error = "Integration revoked before delivery."
        self._db.commit()

    def list_webhook_deliveries(
        self, organization_id: int, endpoint_id: int, limit: int = 50
    ) -> list[WebhookDelivery]:
        self._get_webhook_endpoint(organization_id, endpoint_id)
        return list(self._db.scalars(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.organization_id == organization_id,
                WebhookDelivery.endpoint_id == endpoint_id,
            )
            .order_by(WebhookDelivery.created_at.desc(), WebhookDelivery.id.desc())
            .limit(limit)
        ))

    def _get_webhook_endpoint(self, organization_id: int, endpoint_id: int) -> WebhookEndpoint:
        endpoint = self._db.scalar(select(WebhookEndpoint).where(
            WebhookEndpoint.organization_id == organization_id,
            WebhookEndpoint.id == endpoint_id,
        ))
        if endpoint is None:
            raise EntityNotFoundError("External integration not found.")
        return endpoint
