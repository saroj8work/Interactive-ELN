from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from eln_common.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    project_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="in_progress")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class NotebookEntry(Base):
    __tablename__ = "notebook_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), index=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(200), default="Untitled entry")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RecordTag(Base):
    __tablename__ = "record_tags"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "entity_type", "entity_id", "tag"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    entity_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_id: Mapped[int] = mapped_column(index=True)
    tag: Mapped[str] = mapped_column(String(40), index=True)
    created_by_user_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    actor_user_id: Mapped[int] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(48))
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    previous_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RecordSignature(Base):
    __tablename__ = "record_signatures"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(index=True)
    signed_by_user_id: Mapped[int] = mapped_column(index=True)
    meaning: Mapped[str] = mapped_column(String(24))
    comment: Mapped[str] = mapped_column(String(500), default="")
    record_sha256: Mapped[str] = mapped_column(String(64))
    previous_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EntryRevision(Base):
    __tablename__ = "entry_revisions"
    __table_args__ = (
        UniqueConstraint("organization_id", "entry_id", "revision_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("notebook_entries.id"), index=True)
    revision_number: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    changed_by_user_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    catalog_number: Mapped[str] = mapped_column(String(120), default="")
    lot_number: Mapped[str] = mapped_column(String(120), default="")
    expires_on: Mapped[date | None] = mapped_column()
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0"))
    unit: Mapped[str] = mapped_column(String(32))
    low_stock_threshold: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0")
    )
    location_id: Mapped[int | None] = mapped_column(ForeignKey("storage_locations.id"), index=True)
    location: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    changed_by_user_id: Mapped[int] = mapped_column()
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    resulting_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reason: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    project_id: Mapped[int | None] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    sample_type: Mapped[str] = mapped_column(String(80))
    external_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    parent_sample_id: Mapped[int | None] = mapped_column(ForeignKey("samples.id"))
    storage_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("storage_locations.id"), index=True
    )
    storage_location: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_by_user_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class NotebookTemplate(Base):
    __tablename__ = "notebook_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    created_by_user_id: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column(String(160), index=True)
    template_kind: Mapped[str] = mapped_column(String(24), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    sections: Mapped[list[dict[str, str | bool]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class EntryAttachment(Base):
    __tablename__ = "entry_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("notebook_entries.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(64), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(160))
    size_bytes: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by_user_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EquipmentResource(Base):
    __tablename__ = "equipment_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    storage_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("storage_locations.id"), index=True
    )
    location: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(64), default="equipment", index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_by_user_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EquipmentBooking(Base):
    __tablename__ = "equipment_bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("equipment_resources.id"), index=True
    )
    booked_by_user_id: Mapped[int] = mapped_column(index=True)
    project_id: Mapped[int | None] = mapped_column(index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    purpose: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), default="reserved", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LabTask(Base):
    __tablename__ = "lab_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    project_id: Mapped[int] = mapped_column(index=True)
    experiment_id: Mapped[int | None] = mapped_column(index=True)
    assigned_to_user_id: Mapped[int | None] = mapped_column(index=True)
    created_by_user_id: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class StorageLocation(Base):
    __tablename__ = "storage_locations"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("storage_locations.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    location_type: Mapped[str] = mapped_column(String(32), default="room")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_by_user_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WorkflowRule(Base):
    __tablename__ = "workflow_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    project_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(160))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    task_title: Mapped[str] = mapped_column(String(200))
    task_description: Mapped[str] = mapped_column(Text, default="")
    task_priority: Mapped[str] = mapped_column(String(16), default="normal")
    due_days: Mapped[int | None] = mapped_column()
    enabled: Mapped[bool] = mapped_column(default=True)
    created_by_user_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    __table_args__ = (
        UniqueConstraint("organization_id", "rule_id", "transition_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("workflow_rules.id"), index=True)
    transition_id: Mapped[str] = mapped_column(String(36))
    experiment_id: Mapped[int] = mapped_column(index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("lab_tasks.id"), index=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EntryTimestamp(Base):
    __tablename__ = "entry_timestamps"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("notebook_entries.id"), index=True)
    requested_by_user_id: Mapped[int] = mapped_column()
    tsa_url: Mapped[str] = mapped_column(String(500))
    record_sha256: Mapped[str] = mapped_column(String(64))
    snapshot_json: Mapped[str] = mapped_column(Text)
    token_der: Mapped[bytes] = mapped_column()
    tsa_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
