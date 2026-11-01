from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
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


class ExperimentApproval(Base):
    __tablename__ = "experiment_approvals"
    __table_args__ = (
        Index(
            "uq_experiment_approvals_pending",
            "organization_id",
            "experiment_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), index=True)
    requested_by_user_id: Mapped[int] = mapped_column(index=True)
    reviewer_user_id: Mapped[int] = mapped_column(index=True)
    reviewer_user_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    rejection_reviewer_user_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    review_mode: Mapped[str] = mapped_column(String(16), default="sequential")
    active_branch: Mapped[str] = mapped_column(String(16), default="main")
    current_step_index: Mapped[int] = mapped_column(default=0)
    step_history: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    request_comment: Mapped[str] = mapped_column(Text, default="")
    decision_comment: Mapped[str] = mapped_column(Text, default="")
    snapshot_digest: Mapped[str] = mapped_column(String(64))
    decided_by_user_id: Mapped[int | None] = mapped_column()
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    custom_fields: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class InventoryCustomFieldDefinition(Base):
    __tablename__ = "inventory_custom_field_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(120))
    field_type: Mapped[str] = mapped_column(String(16), default="text")
    required: Mapped[bool] = mapped_column(default=False)
    options: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_by_user_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


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
    current_custodian_user_id: Mapped[int] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SampleCustodyTransfer(Base):
    __tablename__ = "sample_custody_transfers"
    __table_args__ = (
        Index(
            "uq_sample_custody_transfers_pending",
            "organization_id",
            "sample_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"), index=True)
    from_user_id: Mapped[int] = mapped_column(index=True)
    to_user_id: Mapped[int] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    request_note: Mapped[str] = mapped_column(Text, default="")
    receipt_note: Mapped[str] = mapped_column(Text, default="")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    __table_args__ = (
        Index(
            "uq_equipment_booking_calendar_event",
            "organization_id",
            "equipment_id",
            "source_calendar_uid",
            "source_calendar_recurrence_id",
            unique=True,
            postgresql_where=text("source_calendar_uid IS NOT NULL"),
            sqlite_where=text("source_calendar_uid IS NOT NULL"),
        ),
    )

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
    source_calendar_uid: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_calendar_recurrence_id: Mapped[str] = mapped_column(String(40), default="", server_default="")
    status: Mapped[str] = mapped_column(String(24), default="reserved", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EquipmentMaintenance(Base):
    __tablename__ = "equipment_maintenance"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment_resources.id"), index=True)
    created_by_user_id: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="")
    service_provider: Mapped[str] = mapped_column(String(200), default="")
    service_contact_email: Mapped[str] = mapped_column(String(320), default="")
    service_contact_phone: Mapped[str] = mapped_column(String(64), default="")
    recurrence_days: Mapped[int | None] = mapped_column()
    recurrence_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    recurrence_anchor_day: Mapped[int | None] = mapped_column(nullable=True)
    recurrence_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default="scheduled", index=True)
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
    trigger_type: Mapped[str] = mapped_column(String(40), default="experiment_status_changed")
    approval_outcome: Mapped[str | None] = mapped_column(String(16))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str | None] = mapped_column(String(32))
    task_title: Mapped[str] = mapped_column(String(200))
    task_description: Mapped[str] = mapped_column(Text, default="")
    task_priority: Mapped[str] = mapped_column(String(16), default="normal")
    due_days: Mapped[int | None] = mapped_column()
    assigned_to_user_id: Mapped[int | None] = mapped_column()
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
