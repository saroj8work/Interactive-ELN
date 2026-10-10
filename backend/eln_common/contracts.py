from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

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


class ExperimentRead(ExperimentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    organization_id: int
    status: Literal["in_progress", "completed", "archived"]
    created_at: datetime
    updated_at: datetime


class EntryCreate(BaseModel):
    title: str = Field(default="Untitled entry", min_length=1, max_length=200)
    content: str = Field(default="", max_length=100_000)


class EntryUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=100_000)


class EntryRead(EntryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    experiment_id: int
    created_at: datetime
    updated_at: datetime


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
    category: Literal["reagent", "consumable", "equipment"] = "reagent"
    catalog_number: str = Field(default="", max_length=120)
    lot_number: str = Field(default="", max_length=120)
    expires_on: date | None = None
    quantity: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=32)
    low_stock_threshold: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=14, decimal_places=3
    )
    location: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=5000)


class InventoryItemRead(InventoryItemCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime


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
    description: str = Field(default="", max_length=5000)


class SampleRead(SampleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_by_user_id: int
    created_at: datetime


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
    ]
    entity_id: int
    title: str
    detail: str = ""
    project_id: int | None = None


class EquipmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    location: str = Field(default="", max_length=200)


class EquipmentRead(EquipmentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_by_user_id: int
    created_at: datetime


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
    def assume_utc_for_naive_database_timestamps(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
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
