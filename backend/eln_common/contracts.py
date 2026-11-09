from datetime import date, datetime, timezone
from decimal import Decimal
import re
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_at: datetime


class ProjectMemberCreate(BaseModel):
    user_id: int = Field(gt=0)
    role: Literal["editor", "viewer"]


class ProjectMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    project_id: int
    user_id: int
    role: Literal["owner", "editor", "viewer"]


class ProjectAccessRead(BaseModel):
    project_id: int
    role: Literal["admin", "owner", "editor", "viewer"]


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)


class ExperimentStatusUpdate(BaseModel):
    status: Literal["in_progress", "completed", "archived"]


class ExperimentRead(ExperimentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    organization_id: int
    status: Literal["in_progress", "completed", "archived"]
    created_at: datetime
    updated_at: datetime


class ExperimentApprovalRequest(BaseModel):
    reviewer_user_ids: list[int] = Field(min_length=1, max_length=10)
    rejection_reviewer_user_ids: list[int] = Field(default_factory=list, max_length=10)
    review_mode: Literal["sequential", "parallel"] = "sequential"
    comment: str = Field(default="", max_length=2000)

    @field_validator("reviewer_user_ids")
    @classmethod
    def validate_reviewers(cls, value: list[int]) -> list[int]:
        if any(reviewer_id <= 0 for reviewer_id in value):
            raise ValueError("Reviewer IDs must be positive.")
        if len(set(value)) != len(value):
            raise ValueError("A reviewer can only appear once in the approval sequence.")
        return value

    @model_validator(mode="after")
    def validate_rejection_path(self):
        if self.rejection_reviewer_user_ids:
            if self.review_mode != "sequential":
                raise ValueError("A rejection review path requires sequential review mode.")
            if any(user_id <= 0 for user_id in self.rejection_reviewer_user_ids):
                raise ValueError("Reviewer IDs must be positive.")
            if len(set(self.rejection_reviewer_user_ids)) != len(self.rejection_reviewer_user_ids):
                raise ValueError("A reviewer can only appear once in the approval paths.")
            if set(self.reviewer_user_ids) & set(self.rejection_reviewer_user_ids):
                raise ValueError("A reviewer cannot appear in both approval paths.")
        return self


class ExperimentApprovalDecision(BaseModel):
    status: Literal["approved", "rejected"]
    comment: str = Field(default="", max_length=2000)


class ExperimentApprovalStepRead(BaseModel):
    step_order: int
    branch: Literal["main", "rejection"] = "main"
    reviewer_user_id: int
    status: Literal["pending", "approved", "rejected", "stale", "not_required"]
    comment: str = ""
    decided_by_user_id: int | None = None
    decided_at: datetime | None = None


class ExperimentApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    experiment_id: int
    requested_by_user_id: int
    reviewer_user_id: int
    reviewer_user_ids: list[int]
    rejection_reviewer_user_ids: list[int] = Field(default_factory=list)
    review_mode: Literal["sequential", "parallel"]
    active_branch: Literal["main", "rejection"] = "main"
    current_step_index: int
    step_history: list[ExperimentApprovalStepRead]
    status: Literal["pending", "approved", "rejected", "stale"]
    request_comment: str
    decision_comment: str
    snapshot_digest: str
    decided_by_user_id: int | None
    requested_at: datetime
    decided_at: datetime | None


class EntryCreate(BaseModel):
    title: str = Field(default="Untitled entry", min_length=1, max_length=200)
    content: str = Field(default="", max_length=100_000)


class EntryUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=100_000)


class ProjectImportAttachment(BaseModel):
    archive_path: str = Field(min_length=1, max_length=512)
    original_filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(default="application/octet-stream", max_length=160)


class ProjectImportEntry(EntryCreate):
    tags: list[str] = Field(default_factory=list, max_length=20)
    attachments: list[ProjectImportAttachment] = Field(default_factory=list, max_length=100)


class ProjectImportExperimentInfo(ExperimentCreate):
    id: int | None = Field(default=None, gt=0)
    status: Literal["in_progress", "completed", "archived"] = "in_progress"


class ProjectImportExperiment(BaseModel):
    experiment: ProjectImportExperimentInfo
    tags: list[str] = Field(default_factory=list, max_length=20)
    entries: list[ProjectImportEntry] = Field(default_factory=list, max_length=5000)


class ProjectImportTask(BaseModel):
    experiment_id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    due_at: datetime | None = None
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    status: Literal["open", "in_progress", "blocked", "completed", "cancelled"] = "open"

    @field_validator("due_at")
    @classmethod
    def validate_due_at_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Task due date must include a timezone.")
        return value


class ProjectImportPayload(BaseModel):
    format_version: Literal[1] = 1
    project: ProjectCreate
    experiments: list[ProjectImportExperiment] = Field(max_length=1000)
    tasks: list[ProjectImportTask] = Field(default_factory=list, max_length=5000)


class ProjectImportResult(BaseModel):
    project_id: int
    experiments_imported: int
    entries_imported: int
    attachments_imported: int
    tasks_imported: int
    resources_imported: int = 0
    samples_imported: int = 0


class EntryRead(EntryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    experiment_id: int
    created_at: datetime
    updated_at: datetime


class RecordTagSetUpdate(BaseModel):
    entity_type: Literal[
        "experiment", "entry", "inventory", "sample", "equipment", "template"
    ]
    tags: list[str] = Field(max_length=20)


class RecordTagSetRead(BaseModel):
    entity_type: Literal[
        "experiment", "entry", "inventory", "sample", "equipment", "template"
    ]
    entity_id: int
    tags: list[str]


class EntryRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    entry_id: int
    revision_number: int
    title: str
    content: str
    changed_by_user_id: int
    created_at: datetime


class EntryRevisionRestore(BaseModel):
    revision_id: int = Field(gt=0)


class InventoryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(default="reagent", min_length=1, max_length=64)
    catalog_number: str = Field(default="", max_length=120)
    lot_number: str = Field(default="", max_length=120)
    expires_on: date | None = None
    quantity: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=32)
    low_stock_threshold: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=14, decimal_places=3
    )
    location: str = Field(default="", max_length=200)
    location_id: int | None = Field(default=None, gt=0)
    notes: str = Field(default="", max_length=5000)
    custom_fields: dict[str, str] = Field(default_factory=dict)

    @field_validator("custom_fields")
    @classmethod
    def validate_custom_fields(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 50:
            raise ValueError("Inventory supports at most 50 custom fields.")
        total_chars = 0
        for name, field_value in value.items():
            if not name.strip() or len(name) > 120 or len(field_value) > 10_000:
                raise ValueError("Custom field names and values exceed their limits.")
            total_chars += len(name) + len(field_value)
        if total_chars > 100_000:
            raise ValueError("Custom fields exceed the 100,000 character limit.")
        return value


class InventoryItemRead(InventoryItemCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime
    status: Literal["active", "archived", "operational"]


class InventoryCustomFieldDefinitionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    field_type: Literal["text", "number", "date", "boolean", "select"] = "text"
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[str]) -> list[str]:
        normalized = [option.strip() for option in value]
        if any(not option or len(option) > 120 for option in normalized):
            raise ValueError("Select options must be non-empty and at most 120 characters.")
        if len({option.casefold() for option in normalized}) != len(normalized):
            raise ValueError("Select options must be unique.")
        return normalized

    @model_validator(mode="after")
    def validate_select_options(self) -> "InventoryCustomFieldDefinitionCreate":
        if self.field_type == "select" and not self.options:
            raise ValueError("Select fields require at least one option.")
        if self.field_type != "select" and self.options:
            raise ValueError("Only select fields can have options.")
        return self


class InventoryCustomFieldDefinitionUpdate(InventoryCustomFieldDefinitionCreate):
    pass


class InventoryCustomFieldDefinitionRead(InventoryCustomFieldDefinitionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_by_user_id: int
    created_at: datetime
    status: Literal["active", "archived", "operational"]


class StorageLocationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    parent_id: int | None = Field(default=None, gt=0)
    location_type: Literal[
        "building", "room", "freezer", "refrigerator", "cabinet", "shelf", "box", "other"
    ] = "room"
    description: str = Field(default="", max_length=2000)


class StorageLocationRead(StorageLocationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    status: Literal["active", "archived", "operational"]
    created_by_user_id: int
    created_at: datetime


class StorageLocationUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    parent_id: int | None = Field(default=None, gt=0)
    location_type: Literal[
        "building", "room", "freezer", "refrigerator", "cabinet", "shelf", "box", "other"
    ] | None = None
    description: str | None = Field(default=None, max_length=2000)


class WorkflowRuleCreate(BaseModel):
    project_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=160)
    trigger_type: Literal[
        "experiment_status_changed",
        "experiment_created",
        "entry_created",
        "experiment_approval_ended",
    ] = "experiment_status_changed"
    approval_outcome: Literal["approved", "rejected", "stale"] | None = None
    from_status: Literal["in_progress", "completed", "archived"] | None = None
    to_status: Literal["in_progress", "completed", "archived"] | None = None
    task_title: str = Field(min_length=1, max_length=200)
    task_description: str = Field(default="", max_length=5000)
    task_priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_days: int | None = Field(default=None, ge=0, le=3650)
    assigned_to_user_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_trigger_configuration(self) -> "WorkflowRuleCreate":
        if self.trigger_type == "experiment_status_changed":
            if self.approval_outcome is not None:
                raise ValueError("Approval outcomes only apply to approval-ended triggers.")
            if self.to_status is None:
                raise ValueError("Choose a destination status for this trigger.")
            if self.from_status == self.to_status:
                raise ValueError("Workflow transition statuses must differ.")
        elif self.trigger_type == "experiment_approval_ended":
            if self.from_status is not None or self.to_status is not None:
                raise ValueError("Status conditions only apply to experiment status triggers.")
        elif self.from_status is not None or self.to_status is not None or self.approval_outcome is not None:
            raise ValueError("Conditions do not apply to this workflow trigger.")
        return self


class WorkflowRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    trigger_type: Literal[
        "experiment_status_changed",
        "experiment_created",
        "entry_created",
        "experiment_approval_ended",
    ] | None = None
    approval_outcome: Literal["approved", "rejected", "stale"] | None = None
    from_status: Literal["in_progress", "completed", "archived"] | None = None
    to_status: Literal["in_progress", "completed", "archived"] | None = None
    task_title: str | None = Field(default=None, min_length=1, max_length=200)
    task_description: str | None = Field(default=None, max_length=5000)
    task_priority: Literal["low", "normal", "high", "urgent"] | None = None
    due_days: int | None = Field(default=None, ge=0, le=3650)
    assigned_to_user_id: int | None = Field(default=None, gt=0)


class WorkflowRuleEnabledUpdate(BaseModel):
    enabled: bool


class WorkflowRuleRead(WorkflowRuleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    enabled: bool
    created_by_user_id: int
    created_at: datetime


class EntryTimestampRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    entry_id: int
    requested_by_user_id: int
    tsa_url: str
    record_sha256: str
    tsa_time: datetime
    created_at: datetime

    @field_validator("tsa_time", "created_at", mode="before")
    @classmethod
    def assume_utc_for_naive_database_timestamps(cls, value: Any) -> Any:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class EntryTimestampVerificationRead(BaseModel):
    timestamp_id: int
    snapshot_sha256: str
    recorded_sha256: str
    digest_matches: bool
    token_valid_for_snapshot: bool
    token_time: datetime | None
    stored_time_matches: bool
    valid: bool
    message: str


class StockAdjustment(BaseModel):
    quantity_delta: Decimal = Field(
        allow_inf_nan=False, max_digits=14, decimal_places=3
    )
    reason: str = Field(min_length=1, max_length=240)


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    item_id: int
    changed_by_user_id: int
    quantity_delta: Decimal
    resulting_quantity: Decimal
    reason: str
    created_at: datetime


class SampleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    sample_type: str = Field(min_length=1, max_length=80)
    external_id: str = Field(default="", max_length=120)
    project_id: int | None = Field(default=None, gt=0)
    parent_sample_id: int | None = Field(default=None, gt=0)
    storage_location: str = Field(default="", max_length=200)
    storage_location_id: int | None = Field(default=None, gt=0)
    description: str = Field(default="", max_length=5000)


class SampleLocationUpdate(BaseModel):
    storage_location_id: int | None = Field(default=None, gt=0)
    storage_location: str = Field(default="", max_length=200)


class SampleCustodyTransferCreate(BaseModel):
    to_user_id: int = Field(gt=0)
    request_note: str = Field(default="", max_length=2000)


class SampleCustodyTransferAccept(BaseModel):
    receipt_note: str = Field(default="", max_length=2000)


class SampleCustodyTransferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    sample_id: int
    from_user_id: int
    to_user_id: int
    status: Literal["pending", "accepted", "cancelled"]
    request_note: str
    receipt_note: str
    requested_at: datetime
    accepted_at: datetime | None


class SampleRead(SampleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_by_user_id: int
    current_custodian_user_id: int
    created_at: datetime
    status: Literal["active", "archived", "operational"]


class TemplateSection(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    instructions: str = Field(default="", max_length=5000)
    required: bool = False


class NotebookTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    template_kind: Literal["entry", "protocol"]
    description: str = Field(default="", max_length=5000)
    sections: list[TemplateSection] = Field(min_length=1, max_length=40)


class NotebookTemplateUpdate(NotebookTemplateCreate):
    pass


class NotebookTemplateRead(NotebookTemplateCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime
    status: Literal["active", "archived", "operational"]


class ResourceStatusUpdate(BaseModel):
    status: Literal["active", "archived", "operational"]


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    entry_id: int
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    uploaded_by_user_id: int
    created_at: datetime


class SearchHit(BaseModel):
    entity_type: Literal[
        "project",
        "experiment",
        "entry",
        "inventory",
        "sample",
        "template",
        "equipment",
    ]
    entity_id: int
    title: str
    detail: str = ""
    project_id: int | None = None


class EquipmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    location: str = Field(default="", max_length=200)
    storage_location_id: int | None = Field(default=None, gt=0)
    category: str = Field(default="equipment", min_length=1, max_length=64)


class EquipmentRead(EquipmentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_by_user_id: int
    created_at: datetime
    status: Literal["active", "archived", "operational"]


class TaskCreate(BaseModel):
    project_id: int = Field(gt=0)
    experiment_id: int | None = Field(default=None, gt=0)
    assigned_to_user_id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    due_at: datetime | None = None
    priority: Literal["low", "normal", "high", "urgent"] = "normal"

    @field_validator("due_at")
    @classmethod
    def validate_due_at_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Task due date must include a timezone.")
        return value


class TaskStatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "blocked", "completed", "cancelled"]


class TaskRead(TaskCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_by_user_id: int
    status: Literal["open", "in_progress", "blocked", "completed", "cancelled"]
    created_at: datetime
    updated_at: datetime


class RecordSignatureCreate(BaseModel):
    entity_type: Literal["entry"]
    entity_id: int = Field(gt=0)
    meaning: Literal["authored", "reviewed", "approved"]
    comment: str = Field(default="", max_length=500)
    password: str | None = Field(default=None, max_length=128)


class RecordSignatureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    entity_type: str
    entity_id: int
    signed_by_user_id: int
    meaning: str
    comment: str
    record_sha256: str
    previous_hash: str
    event_hash: str
    created_at: datetime


class AuditVerificationRead(BaseModel):
    organization_id: int
    valid: bool
    checked_events: int


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    actor_user_id: int
    action: str
    entity_type: str
    entity_id: int
    payload_json: str
    previous_hash: str
    event_hash: str
    created_at: datetime


class InboundInstrumentPayload(BaseModel):
    instrument_name: str = Field(min_length=1, max_length=160)
    experiment_id: int | None = None
    entry_id: int | None = None
    measurement_type: str = Field(default="measurement", max_length=80)
    readings: list[dict[str, Any]] = Field(default_factory=list)
    raw_data: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EquipmentBookingCreate(BaseModel):
    starts_at: datetime
    ends_at: datetime
    purpose: str = Field(min_length=1, max_length=500)
    project_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_time_range(self) -> "EquipmentBookingCreate":
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("Booking timestamps must include a timezone.")
        if self.ends_at <= self.starts_at:
            raise ValueError("Booking end must be after booking start.")
        return self


class RecurringEquipmentBookingCreate(BaseModel):
    starts_at: datetime
    ends_at: datetime
    purpose: str = Field(min_length=1, max_length=500)
    project_id: int | None = Field(default=None, gt=0)
    recurrence_unit: Literal["day", "week", "month"] = Field(default="week")
    recurrence_interval: int = Field(default=1, ge=1, le=30)
    recurrence_count: int | None = Field(default=None, ge=1, le=50)
    recurrence_until: date | None = None

    @model_validator(mode="after")
    def validate_recurring_parameters(self) -> "RecurringEquipmentBookingCreate":
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("Booking timestamps must include a timezone.")
        if self.ends_at <= self.starts_at:
            raise ValueError("Booking end must be after booking start.")
        if self.recurrence_count is None and self.recurrence_until is None:
            raise ValueError("Specify either recurrence_count or recurrence_until.")
        return self


class EquipmentBookingBatchCreate(BaseModel):
    bookings: list[EquipmentBookingCreate] = Field(min_length=1, max_length=100)


class EquipmentBookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    equipment_id: int
    booked_by_user_id: int
    starts_at: datetime
    ends_at: datetime
    purpose: str
    project_id: int | None
    status: Literal["reserved", "cancelled", "completed"]
    created_at: datetime

    @field_validator("starts_at", "ends_at", mode="before")
    @classmethod
    def assume_utc_for_naive_database_timestamps(cls, value: Any) -> Any:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class EquipmentCalendarImportResult(BaseModel):
    imported_count: int = Field(ge=0)


class EquipmentMaintenanceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=5000)
    service_provider: str = Field(default="", max_length=200)
    service_contact_email: str = Field(default="", max_length=320)
    service_contact_phone: str = Field(default="", max_length=64)
    recurrence_days: int | None = Field(default=None, ge=1, le=3650)
    recurrence_unit: Literal["days", "weeks", "months"] | None = None
    recurrence_until: date | None = None
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def validate_window(self) -> "EquipmentMaintenanceCreate":
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("Maintenance timestamps must include a timezone.")
        if self.ends_at <= self.starts_at:
            raise ValueError("Maintenance end must be after maintenance start.")
        if self.recurrence_until is not None:
            if self.recurrence_days is None:
                raise ValueError("A recurrence end date requires a recurrence interval.")
            if self.recurrence_until < self.starts_at.date():
                raise ValueError("Recurrence end date cannot precede the first maintenance window.")
        return self


class EquipmentMaintenanceStatusUpdate(BaseModel):
    status: Literal["in_progress", "completed", "cancelled"]


class EquipmentMaintenanceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=5000)
    service_provider: str | None = Field(default=None, max_length=200)
    service_contact_email: str | None = Field(default=None, max_length=320)
    service_contact_phone: str | None = Field(default=None, max_length=64)
    recurrence_days: int | None = Field(default=None, ge=1, le=3650)
    recurrence_unit: Literal["days", "weeks", "months"] | None = None
    recurrence_until: date | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone_for_updated_window(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Maintenance timestamps must include a timezone.")
        return value


class EquipmentMaintenanceRead(EquipmentMaintenanceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    equipment_id: int
    created_by_user_id: int
    status: Literal["scheduled", "in_progress", "completed", "cancelled"]
    created_at: datetime

    @field_validator("starts_at", "ends_at", "created_at", mode="before")
    @classmethod
    def assume_utc_for_naive_timestamps(cls, value: datetime) -> datetime:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class ActivityEventCreate(BaseModel):
    event_id: str = Field(min_length=1, max_length=36)
    source_service: str = Field(min_length=1, max_length=64)
    action: str = Field(min_length=1, max_length=48)
    entity_type: str = Field(min_length=1, max_length=48)
    entity_id: int
    organization_id: int
    occurred_at: datetime
    details: dict[str, str] = Field(default_factory=dict)


class WebhookEndpointCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2048)
    event_types: list[str] = Field(min_length=1, max_length=50)

    @field_validator("url")
    @classmethod
    def require_https_url_without_embedded_credentials(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Webhook URL must be HTTPS and cannot contain credentials, query parameters, or a fragment.")
        return value.strip()

    @field_validator("event_types")
    @classmethod
    def validate_webhook_event_types(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(item.strip().casefold() for item in value))
        if "*" in normalized and len(normalized) != 1:
            raise ValueError("The wildcard event type cannot be combined with specific event types.")
        if any(
            item != "*"
            and not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}\.[a-z][a-z0-9_-]{0,47}", item)
            for item in normalized
        ):
            raise ValueError("Event types must use source.action names, such as notebook.created.")
        return normalized


class WebhookEndpointUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    event_types: list[str] | None = Field(default=None, min_length=1, max_length=50)
    enabled: bool | None = None

    @field_validator("url")
    @classmethod
    def validate_optional_https_url(cls, value: str | None) -> str | None:
        return WebhookEndpointCreate.require_https_url_without_embedded_credentials(value) if value is not None else None

    @field_validator("event_types")
    @classmethod
    def validate_optional_event_types(cls, value: list[str] | None) -> list[str] | None:
        return WebhookEndpointCreate.validate_webhook_event_types(value) if value is not None else None


class WebhookEndpointRead(BaseModel):
    id: int
    name: str
    url: str
    event_types: list[str]
    secret_prefix: str
    enabled: bool
    created_at: datetime
    revoked_at: datetime | None


class WebhookEndpointCreated(WebhookEndpointRead):
    secret: str


class WebhookDeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: str
    event_type: str
    attempts: int
    next_attempt_at: datetime | None
    last_attempt_at: datetime | None
    last_status_code: int | None
    last_error: str | None
    delivered_at: datetime | None
    failed_at: datetime | None
    created_at: datetime


class ActivityEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: str
    source_service: str
    action: str
    entity_type: str
    entity_id: int
    organization_id: int
    occurred_at: datetime
    details: dict[str, str]


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    user_id: int
    event_id: str
    title: str
    message: str
    entity_type: str
    entity_id: int
    details: dict[str, str]
    created_at: datetime
    read_at: datetime | None


class PlateWellRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    coordinate: str
    row_letter: str
    col_number: int
    role: str
    sample_name: str
    sample_id: int | None
    replicate_group: str
    standard_concentration: float | None
    concentration_unit: str
    dilution_factor: float
    raw_value: float | None
    corrected_value: float | None
    calculated_concentration: float | None


class MicroplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    project_id: int | None
    experiment_id: int | None
    name: str
    plate_format: str
    rows: int
    cols: int
    description: str
    assay_type: str
    wavelength: str
    measurement_unit: str
    created_at: datetime
    updated_at: datetime
    wells: list[PlateWellRead]



class ChemicalCompoundRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    project_id: int | None = None
    experiment_id: int | None = None
    name: str
    smiles: str
    formula: str
    molecular_weight: float
    monoisotopic_mass: float
    logp: float
    hbd: int
    hba: int
    rotatable_bonds: int
    tpsa: float
    rule_of_five_violations: int
    drug_likeness_score: float
    ghs_hazard_codes: str
    ghs_pictograms: str
    svg_depiction: str
    created_at: datetime


class ChemicalAnalysisResult(BaseModel):
    name: str
    smiles: str
    formula: str
    molecular_weight: float
    monoisotopic_mass: float
    logp: float
    hbd: int
    hba: int
    rotatable_bonds: int
    tpsa: float
    rule_of_five_violations: int
    drug_likeness_score: float
    ghs_hazard_codes: str
    ghs_pictograms: str
    svg_depiction: str
