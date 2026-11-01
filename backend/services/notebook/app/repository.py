from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import delete, func, literal_column, or_, select, update
from sqlalchemy.orm import Session

from .models import (
    Experiment,
    AuditEvent,
    EntryAttachment,
    EntryRevision,
    EquipmentBooking,
    EquipmentMaintenance,
    EquipmentResource,
    InventoryItem,
    LabTask,
    NotebookEntry,
    NotebookTemplate,
    RecordTag,
    RecordSignature,
    Sample,
    SampleCustodyTransfer,
    StockMovement,
)


_SIMPLE_CONFIG = literal_column("'simple'::regconfig")
_EMPTY_TEXT = literal_column("''")
_SPACE_TEXT = literal_column("' '")


def _search_text(columns, query: str, pattern: str, *, postgres: bool):
    if postgres:
        document = func.coalesce(columns[0], _EMPTY_TEXT)
        for column in columns[1:]:
            document = document.op("||")(_SPACE_TEXT).op("||")(
                func.coalesce(column, _EMPTY_TEXT)
            )
        return func.to_tsvector(_SIMPLE_CONFIG, document).op("@@")(
            func.plainto_tsquery(_SIMPLE_CONFIG, query)
        )
    return or_(*(column.ilike(pattern, escape="\\") for column in columns))

class NotebookRepository:
    def __init__(self, db: Session):
        self._db = db

    def list_experiments(
        self, organization_id: int, project_id: int
    ) -> list[Experiment]:
        return list(
            self._db.scalars(
                select(Experiment)
                .where(
                    Experiment.organization_id == organization_id,
                    Experiment.project_id == project_id,
                )
                .order_by(Experiment.updated_at.desc())
            )
        )

    def get_experiment(
        self, organization_id: int, experiment_id: int
    ) -> Experiment | None:
        return self._db.scalar(
            select(Experiment).where(
                Experiment.id == experiment_id,
                Experiment.organization_id == organization_id,
            )
        )

    def add_experiment(self, experiment: Experiment) -> Experiment:
        self._db.add(experiment)
        self._db.flush()
        return experiment

    def list_entries(
        self, organization_id: int, experiment_id: int
    ) -> list[NotebookEntry]:
        return list(
            self._db.scalars(
                select(NotebookEntry)
                .where(
                    NotebookEntry.organization_id == organization_id,
                    NotebookEntry.experiment_id == experiment_id,
                )
                .order_by(NotebookEntry.updated_at.desc())
            )
        )

    def get_entry(self, organization_id: int, entry_id: int) -> NotebookEntry | None:
        return self._db.scalar(
            select(NotebookEntry).where(
                NotebookEntry.id == entry_id,
                NotebookEntry.organization_id == organization_id,
            )
        )

    def add_entry(self, entry: NotebookEntry) -> NotebookEntry:
        self._db.add(entry)
        self._db.flush()
        return entry

    def get_record_project_id(
        self, organization_id: int, entity_type: str, entity_id: int
    ) -> int | None:
        if entity_type == "experiment":
            return self._db.scalar(
                select(Experiment.project_id).where(
                    Experiment.organization_id == organization_id,
                    Experiment.id == entity_id,
                )
            )
        if entity_type == "entry":
            return self._db.scalar(
                select(Experiment.project_id)
                .join(NotebookEntry, NotebookEntry.experiment_id == Experiment.id)
                .where(
                    NotebookEntry.organization_id == organization_id,
                    NotebookEntry.id == entity_id,
                    Experiment.organization_id == organization_id,
                )
            )
        if entity_type == "inventory":
            return (
                0
                if self._db.scalar(
                    select(InventoryItem.id).where(
                        InventoryItem.organization_id == organization_id,
                        InventoryItem.id == entity_id,
                        InventoryItem.status == "active",
                    )
                )
                is not None
                else None
            )
        if entity_type == "sample":
            return self._db.scalar(
                select(Sample.project_id).where(
                    Sample.organization_id == organization_id,
                    Sample.id == entity_id,
                    Sample.status == "active",
                )
            )
        if entity_type == "equipment":
            return (
                0
                if self._db.scalar(
                    select(EquipmentResource.id).where(
                        EquipmentResource.organization_id == organization_id,
                        EquipmentResource.id == entity_id,
                        EquipmentResource.status == "active",
                    )
                )
                is not None
                else None
            )
        if entity_type == "template":
            return (
                0
                if self._db.scalar(
                    select(NotebookTemplate.id).where(
                        NotebookTemplate.organization_id == organization_id,
                        NotebookTemplate.id == entity_id,
                        NotebookTemplate.status == "active",
                    )
                )
                is not None
                else None
            )
        raise ValueError("Unsupported tag entity type.")

    def record_tag_target(
        self, organization_id: int, entity_type: str, entity_id: int
    ) -> tuple[bool, int | None]:
        if entity_type in {"experiment", "entry"}:
            project_id = self.get_record_project_id(
                organization_id, entity_type, entity_id
            )
            return project_id is not None, project_id
        model = {
            "inventory": InventoryItem,
            "sample": Sample,
            "equipment": EquipmentResource,
            "template": NotebookTemplate,
        }.get(entity_type)
        if model is None:
            return False, None
        record = self._db.scalar(
            select(model).where(
                model.organization_id == organization_id,
                model.id == entity_id,
                model.status == "active",
            )
        )
        if record is None:
            return False, None
        return True, getattr(record, "project_id", None)

    def list_record_tags(
        self, organization_id: int, entity_type: str, entity_id: int
    ) -> list[str]:
        return list(
            self._db.scalars(
                select(RecordTag.tag)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == entity_type,
                    RecordTag.entity_id == entity_id,
                )
                .order_by(RecordTag.tag)
            )
        )

    def list_project_record_tags(
        self, organization_id: int, project_id: int
    ) -> dict[tuple[str, int], list[str]]:
        experiment_ids = set(
            self._db.scalars(
                select(Experiment.id).where(
                    Experiment.organization_id == organization_id,
                    Experiment.project_id == project_id,
                )
            )
        )
        entry_ids = set(
            self._db.scalars(
                select(NotebookEntry.id)
                .join(Experiment, NotebookEntry.experiment_id == Experiment.id)
                .where(
                    NotebookEntry.organization_id == organization_id,
                    Experiment.organization_id == organization_id,
                    Experiment.project_id == project_id,
                )
            )
        )
        tags: dict[tuple[str, int], list[str]] = {}
        rows = self._db.execute(
            select(RecordTag.entity_type, RecordTag.entity_id, RecordTag.tag).where(
                RecordTag.organization_id == organization_id,
                RecordTag.entity_type.in_(("experiment", "entry")),
            )
        )
        for entity_type, entity_id, tag in rows:
            allowed_ids = experiment_ids if entity_type == "experiment" else entry_ids
            if entity_id in allowed_ids:
                tags.setdefault((entity_type, entity_id), []).append(tag)
        return tags

    def replace_record_tags(
        self,
        organization_id: int,
        entity_type: str,
        entity_id: int,
        user_id: int,
        tags: list[str],
    ) -> None:
        self._db.execute(
            delete(RecordTag).where(
                RecordTag.organization_id == organization_id,
                RecordTag.entity_type == entity_type,
                RecordTag.entity_id == entity_id,
            )
        )
        self._db.add_all(
            RecordTag(
                organization_id=organization_id,
                entity_type=entity_type,
                entity_id=entity_id,
                tag=tag,
                created_by_user_id=user_id,
            )
            for tag in tags
        )
        self._db.flush()

    def next_revision_number(self, organization_id: int, entry_id: int) -> int:
        latest = self._db.scalar(
            select(func.max(EntryRevision.revision_number)).where(
                EntryRevision.organization_id == organization_id,
                EntryRevision.entry_id == entry_id,
            )
        )
        return (latest or 0) + 1

    def add_revision(self, revision: EntryRevision) -> EntryRevision:
        self._db.add(revision)
        self._db.flush()
        return revision

    def list_revisions(
        self, organization_id: int, entry_id: int
    ) -> list[EntryRevision]:
        return list(
            self._db.scalars(
                select(EntryRevision)
                .where(
                    EntryRevision.organization_id == organization_id,
                    EntryRevision.entry_id == entry_id,
                )
                .order_by(EntryRevision.revision_number.desc())
            )
        )

    def get_revision(
        self, organization_id: int, entry_id: int, revision_id: int
    ) -> EntryRevision | None:
        return self._db.scalar(
            select(EntryRevision).where(
                EntryRevision.organization_id == organization_id,
                EntryRevision.entry_id == entry_id,
                EntryRevision.id == revision_id,
            )
        )

    def list_inventory(self, organization_id: int) -> list[InventoryItem]:
        return list(
            self._db.scalars(
                select(InventoryItem)
                .where(
                    InventoryItem.organization_id == organization_id,
                )
                .order_by(InventoryItem.name, InventoryItem.id)
            )
        )

    def get_inventory_item(
        self, organization_id: int, item_id: int
    ) -> InventoryItem | None:
        return self._db.scalar(
            select(InventoryItem).where(
                InventoryItem.organization_id == organization_id,
                InventoryItem.id == item_id,
            )
        )

    def change_inventory_quantity(
        self, organization_id: int, item_id: int, delta: Decimal
    ) -> int:
        result = self._db.execute(
            update(InventoryItem)
            .where(
                InventoryItem.organization_id == organization_id,
                InventoryItem.id == item_id,
                InventoryItem.quantity + delta >= 0,
            )
            .values(quantity=InventoryItem.quantity + delta)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount or 0

    def add_inventory_item(self, item: InventoryItem) -> InventoryItem:
        self._db.add(item)
        self._db.flush()
        return item

    def add_stock_movement(self, movement: StockMovement) -> StockMovement:
        self._db.add(movement)
        self._db.flush()
        return movement

    def list_stock_movements(
        self, organization_id: int, item_id: int
    ) -> list[StockMovement]:
        return list(
            self._db.scalars(
                select(StockMovement)
                .where(
                    StockMovement.organization_id == organization_id,
                    StockMovement.item_id == item_id,
                )
                .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
            )
        )

    def list_samples(self, organization_id: int) -> list[Sample]:
        return list(
            self._db.scalars(
                select(Sample)
                .where(
                    Sample.organization_id == organization_id,
                )
                .order_by(Sample.created_at.desc(), Sample.id.desc())
            )
        )

    def get_sample(
        self, organization_id: int, sample_id: int, *, lock: bool = False
    ) -> Sample | None:
        statement = select(Sample).where(
            Sample.organization_id == organization_id, Sample.id == sample_id
        )
        if lock:
            statement = statement.with_for_update()
        return self._db.scalar(statement)

    def add_sample_custody_transfer(self, transfer: SampleCustodyTransfer) -> SampleCustodyTransfer:
        self._db.add(transfer)
        self._db.flush()
        return transfer

    def get_sample_custody_transfer(
        self, organization_id: int, sample_id: int, transfer_id: int, *, lock: bool = False
    ) -> SampleCustodyTransfer | None:
        statement = select(SampleCustodyTransfer).where(
            SampleCustodyTransfer.organization_id == organization_id,
            SampleCustodyTransfer.sample_id == sample_id,
            SampleCustodyTransfer.id == transfer_id,
        )
        if lock:
            statement = statement.with_for_update()
        return self._db.scalar(statement)

    def get_pending_sample_custody_transfer(
        self, organization_id: int, sample_id: int
    ) -> SampleCustodyTransfer | None:
        return self._db.scalar(select(SampleCustodyTransfer).where(
            SampleCustodyTransfer.organization_id == organization_id,
            SampleCustodyTransfer.sample_id == sample_id,
            SampleCustodyTransfer.status == "pending",
        ))

    def list_sample_custody_transfers(
        self, organization_id: int, sample_id: int
    ) -> list[SampleCustodyTransfer]:
        return list(self._db.scalars(select(SampleCustodyTransfer).where(
            SampleCustodyTransfer.organization_id == organization_id,
            SampleCustodyTransfer.sample_id == sample_id,
        ).order_by(SampleCustodyTransfer.requested_at, SampleCustodyTransfer.id)))

    def list_pending_sample_custody_transfers_for_user(
        self, organization_id: int, user_id: int
    ) -> list[SampleCustodyTransfer]:
        return list(self._db.scalars(select(SampleCustodyTransfer).where(
            SampleCustodyTransfer.organization_id == organization_id,
            SampleCustodyTransfer.status == "pending",
            or_(
                SampleCustodyTransfer.from_user_id == user_id,
                SampleCustodyTransfer.to_user_id == user_id,
            ),
        ).order_by(SampleCustodyTransfer.requested_at, SampleCustodyTransfer.id)))

    def has_active_sample_children(self, organization_id: int, sample_id: int) -> bool:
        return self._db.scalar(select(Sample.id).where(
            Sample.organization_id == organization_id,
            Sample.parent_sample_id == sample_id,
            Sample.status == "active",
        ).limit(1)) is not None

    def get_audit_head(self, organization_id: int) -> AuditEvent | None:
        return self._db.scalar(
            select(AuditEvent)
            .where(AuditEvent.organization_id == organization_id)
            .order_by(AuditEvent.id.desc())
            .limit(1)
        )

    def add_audit_event(self, event: AuditEvent) -> AuditEvent:
        self._db.add(event)
        self._db.flush()
        return event

    def list_audit_events(self, organization_id: int) -> list[AuditEvent]:
        return list(
            self._db.scalars(
                select(AuditEvent)
                .where(AuditEvent.organization_id == organization_id)
                .order_by(AuditEvent.id)
            )
        )

    def list_signatures(
        self, organization_id: int, entity_type: str, entity_id: int
    ) -> list[RecordSignature]:
        return list(
            self._db.scalars(
                select(RecordSignature)
                .where(
                    RecordSignature.organization_id == organization_id,
                    RecordSignature.entity_type == entity_type,
                    RecordSignature.entity_id == entity_id,
                )
                .order_by(RecordSignature.created_at, RecordSignature.id)
            )
        )

    def add_signature(self, signature: RecordSignature) -> RecordSignature:
        self._db.add(signature)
        self._db.flush()
        return signature

    def get_signature(
        self, organization_id: int, signature_id: int
    ) -> RecordSignature | None:
        return self._db.scalar(
            select(RecordSignature).where(
                RecordSignature.organization_id == organization_id,
                RecordSignature.id == signature_id,
            )
        )

    def get_resource(self, organization_id: int, entity_type: str, entity_id: int):
        model = {
            "inventory": InventoryItem,
            "sample": Sample,
            "equipment": EquipmentResource,
            "template": NotebookTemplate,
        }.get(entity_type)
        if model is None:
            raise ValueError("Unsupported resource type.")
        return self._db.scalar(
            select(model).where(
                model.organization_id == organization_id, model.id == entity_id
            )
        )

    def has_active_equipment_bookings(
        self, organization_id: int, equipment_id: int
    ) -> bool:
        return (
            self._db.scalar(
                select(EquipmentBooking.id)
                .where(
                    EquipmentBooking.organization_id == organization_id,
                    EquipmentBooking.equipment_id == equipment_id,
                    EquipmentBooking.status == "reserved",
                    EquipmentBooking.ends_at > datetime.now(timezone.utc),
                )
                .limit(1)
            )
            is not None
        )

    def has_active_equipment_maintenance(
        self, organization_id: int, equipment_id: int
    ) -> bool:
        return self._db.scalar(select(EquipmentMaintenance.id).where(
            EquipmentMaintenance.organization_id == organization_id,
            EquipmentMaintenance.equipment_id == equipment_id,
            EquipmentMaintenance.status.in_(("scheduled", "in_progress")),
            EquipmentMaintenance.ends_at > datetime.now(timezone.utc),
        ).limit(1)) is not None

    def list_tasks(self, organization_id: int, project_id: int) -> list[LabTask]:
        return list(
            self._db.scalars(
                select(LabTask)
                .where(
                    LabTask.organization_id == organization_id,
                    LabTask.project_id == project_id,
                )
                .order_by(LabTask.due_at.is_(None), LabTask.due_at, LabTask.id)
            )
        )

    def get_task(self, organization_id: int, task_id: int) -> LabTask | None:
        return self._db.scalar(
            select(LabTask).where(
                LabTask.organization_id == organization_id,
                LabTask.id == task_id,
            )
        )

    def add_task(self, task: LabTask) -> LabTask:
        self._db.add(task)
        self._db.flush()
        return task

    def list_organization_tasks(self, organization_id: int) -> list[LabTask]:
        return list(
            self._db.scalars(
                select(LabTask)
                .where(LabTask.organization_id == organization_id)
                .order_by(LabTask.due_at.is_(None), LabTask.due_at, LabTask.id)
            )
        )

    def add_sample(self, sample: Sample) -> Sample:
        self._db.add(sample)
        self._db.flush()
        return sample

    def list_templates(self, organization_id: int) -> list[NotebookTemplate]:
        return list(
            self._db.scalars(
                select(NotebookTemplate)
                .where(
                    NotebookTemplate.organization_id == organization_id,
                )
                .order_by(NotebookTemplate.name, NotebookTemplate.id)
            )
        )

    def get_template(
        self, organization_id: int, template_id: int
    ) -> NotebookTemplate | None:
        return self._db.scalar(
            select(NotebookTemplate).where(
                NotebookTemplate.organization_id == organization_id,
                NotebookTemplate.id == template_id,
            )
        )

    def add_template(self, template: NotebookTemplate) -> NotebookTemplate:
        self._db.add(template)
        self._db.flush()
        return template

    def list_attachments(
        self, organization_id: int, entry_id: int
    ) -> list[EntryAttachment]:
        return list(
            self._db.scalars(
                select(EntryAttachment)
                .where(
                    EntryAttachment.organization_id == organization_id,
                    EntryAttachment.entry_id == entry_id,
                )
                .order_by(EntryAttachment.created_at.desc())
            )
        )

    def get_attachment(
        self, organization_id: int, attachment_id: int
    ) -> EntryAttachment | None:
        return self._db.scalar(
            select(EntryAttachment).where(
                EntryAttachment.organization_id == organization_id,
                EntryAttachment.id == attachment_id,
            )
        )

    def list_equipment(self, organization_id: int) -> list[EquipmentResource]:
        return list(
            self._db.scalars(
                select(EquipmentResource)
                .where(
                    EquipmentResource.organization_id == organization_id,
                )
                .order_by(EquipmentResource.name, EquipmentResource.id)
            )
        )

    def get_equipment(
        self, organization_id: int, equipment_id: int, *, lock: bool = False
    ) -> EquipmentResource | None:
        statement = select(EquipmentResource).where(
            EquipmentResource.organization_id == organization_id,
            EquipmentResource.id == equipment_id,
        )
        if lock:
            statement = statement.with_for_update()
        return self._db.scalar(statement)

    def add_equipment(self, equipment: EquipmentResource) -> EquipmentResource:
        self._db.add(equipment)
        self._db.flush()
        return equipment

    def list_bookings(self, organization_id: int) -> list[EquipmentBooking]:
        return list(
            self._db.scalars(
                select(EquipmentBooking)
                .where(EquipmentBooking.organization_id == organization_id)
                .order_by(EquipmentBooking.starts_at, EquipmentBooking.id)
            )
        )

    def has_booking_conflict(
        self,
        organization_id: int,
        equipment_id: int,
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        return (
            self._db.scalar(
                select(EquipmentBooking.id)
                .where(
                    EquipmentBooking.organization_id == organization_id,
                    EquipmentBooking.equipment_id == equipment_id,
                    EquipmentBooking.status == "reserved",
                    EquipmentBooking.starts_at < ends_at,
                    EquipmentBooking.ends_at > starts_at,
                )
                .limit(1)
            )
            is not None
        )

    def get_booking(
        self, organization_id: int, booking_id: int
    ) -> EquipmentBooking | None:
        return self._db.scalar(
            select(EquipmentBooking).where(
                EquipmentBooking.organization_id == organization_id,
                EquipmentBooking.id == booking_id,
            )
        )

    def add_booking(self, booking: EquipmentBooking) -> EquipmentBooking:
        self._db.add(booking)
        self._db.flush()
        return booking

    def list_maintenance(self, organization_id: int) -> list[EquipmentMaintenance]:
        return list(self._db.scalars(
            select(EquipmentMaintenance)
            .where(EquipmentMaintenance.organization_id == organization_id)
            .order_by(EquipmentMaintenance.starts_at, EquipmentMaintenance.id)
        ))

    def get_maintenance(self, organization_id: int, maintenance_id: int) -> EquipmentMaintenance | None:
        return self._db.scalar(select(EquipmentMaintenance).where(
            EquipmentMaintenance.organization_id == organization_id,
            EquipmentMaintenance.id == maintenance_id,
        ))

    def add_maintenance(self, maintenance: EquipmentMaintenance) -> EquipmentMaintenance:
        self._db.add(maintenance)
        self._db.flush()
        return maintenance

    def has_maintenance_conflict(
        self, organization_id: int, equipment_id: int, starts_at: datetime, ends_at: datetime,
        *, exclude_maintenance_id: int | None = None,
    ) -> bool:
        statement = select(EquipmentMaintenance.id).where(
            EquipmentMaintenance.organization_id == organization_id,
            EquipmentMaintenance.equipment_id == equipment_id,
            EquipmentMaintenance.status.in_(("scheduled", "in_progress")),
            EquipmentMaintenance.starts_at < ends_at,
            EquipmentMaintenance.ends_at > starts_at,
        )
        if exclude_maintenance_id is not None:
            statement = statement.where(EquipmentMaintenance.id != exclude_maintenance_id)
        return self._db.scalar(statement.limit(1)) is not None

    def add_attachment(self, attachment: EntryAttachment) -> EntryAttachment:
        self._db.add(attachment)
        self._db.flush()
        return attachment

    def search(
        self, organization_id: int, query: str
    ) -> list[tuple[str, int, str, str, int | None]]:
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        postgres = self._db.get_bind().dialect.name == "postgresql"

        def matches(*columns):
            return _search_text(columns, query, pattern, postgres=postgres)

        hits: list[tuple[str, int, str, str, int | None]] = []
        experiments = self._db.scalars(
            select(Experiment).where(
                Experiment.organization_id == organization_id,
                matches(Experiment.name, Experiment.description)
                | select(RecordTag.id)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == "experiment",
                    RecordTag.entity_id == Experiment.id,
                    matches(RecordTag.tag),
                )
                .exists(),
            ).limit(100)
        )
        hits.extend(
            ("experiment", item.id, item.name, item.description, item.project_id)
            for item in experiments
        )
        entries = self._db.execute(
            select(NotebookEntry, Experiment.project_id)
            .join(Experiment, NotebookEntry.experiment_id == Experiment.id)
            .where(
                NotebookEntry.organization_id == organization_id,
                Experiment.organization_id == organization_id,
                matches(NotebookEntry.title, NotebookEntry.content)
                | select(RecordTag.id)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == "entry",
                    RecordTag.entity_id == NotebookEntry.id,
                    matches(RecordTag.tag),
                )
                .exists(),
            )
            .limit(100)
        ).all()
        hits.extend(
            ("entry", entry.id, entry.title, entry.content[:240], project_id)
            for entry, project_id in entries
        )
        inventory = self._db.scalars(
            select(InventoryItem)
            .where(
                InventoryItem.organization_id == organization_id,
                InventoryItem.status == "active",
                matches(
                    InventoryItem.name,
                    InventoryItem.category,
                    InventoryItem.catalog_number,
                    InventoryItem.lot_number,
                    InventoryItem.location,
                    InventoryItem.notes,
                )
                | select(RecordTag.id)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == "inventory",
                    RecordTag.entity_id == InventoryItem.id,
                    matches(RecordTag.tag),
                )
                .exists(),
            )
            .limit(100)
        )
        hits.extend(
            ("inventory", item.id, item.name, item.location, None)
            for item in inventory
        )
        samples = self._db.scalars(
            select(Sample)
            .where(
                Sample.organization_id == organization_id,
                Sample.status == "active",
                matches(
                    Sample.name,
                    Sample.external_id,
                    Sample.sample_type,
                    Sample.storage_location,
                    Sample.description,
                )
                | select(RecordTag.id)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == "sample",
                    RecordTag.entity_id == Sample.id,
                    matches(RecordTag.tag),
                )
                .exists(),
            )
            .limit(100)
        )
        hits.extend(
            ("sample", sample.id, sample.name, sample.external_id, sample.project_id)
            for sample in samples
        )
        equipment = self._db.scalars(
            select(EquipmentResource)
            .where(
                EquipmentResource.organization_id == organization_id,
                EquipmentResource.status == "active",
                matches(
                    EquipmentResource.name,
                    EquipmentResource.location,
                    EquipmentResource.category,
                    EquipmentResource.description,
                )
                | select(RecordTag.id)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == "equipment",
                    RecordTag.entity_id == EquipmentResource.id,
                    matches(RecordTag.tag),
                )
                .exists(),
            )
            .limit(100)
        )
        hits.extend(
            ("equipment", item.id, item.name, item.location, None)
            for item in equipment
        )
        templates = self._db.scalars(
            select(NotebookTemplate)
            .where(
                NotebookTemplate.organization_id == organization_id,
                NotebookTemplate.status == "active",
                matches(NotebookTemplate.name, NotebookTemplate.description)
                | select(RecordTag.id)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == "template",
                    RecordTag.entity_id == NotebookTemplate.id,
                    matches(RecordTag.tag),
                )
                .exists(),
            )
            .limit(100)
        )
        hits.extend(
            ("template", template.id, template.name, template.description, None)
            for template in templates
        )
        return hits
