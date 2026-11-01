from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from eln_common.database import Base


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    source_service: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(48), index=True)
    entity_type: Mapped[str] = mapped_column(String(48), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    organization_id: Mapped[int] = mapped_column(Integer, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    details: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", "event_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    user_id: Mapped[int] = mapped_column(index=True)
    event_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(String(500))
    entity_type: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[int] = mapped_column(Integer)
    details: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    created_by_user_id: Mapped[int]
    name: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(2048))
    event_types: Mapped[list[str]] = mapped_column(JSON)
    secret_prefix: Mapped[str] = mapped_column(String(24))
    encrypted_secret: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        UniqueConstraint("endpoint_id", "event_id", name="uq_webhook_delivery_endpoint_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    endpoint_id: Mapped[int] = mapped_column(ForeignKey("webhook_endpoints.id"), index=True)
    event_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(113))
    payload: Mapped[dict] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status_code: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(String(500))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
