from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from .models import (
    Experiment,
    AuditEvent,
    EntryAttachment,
    EntryRevision,
    EquipmentBooking,
    EquipmentResource,
    InventoryItem,
    LabTask,
    NotebookEntry,
    NotebookTemplate,
    RecordTag,
    RecordSignature,
    Sample,
    StockMovement,
)

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

    def get_sample(self, organization_id: int, sample_id: int) -> Sample | None:
        return self._db.scalar(
            select(Sample).where(
                Sample.organization_id == organization_id, Sample.id == sample_id
            )
        )

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

    def add_attachment(self, attachment: EntryAttachment) -> EntryAttachment:
        self._db.add(attachment)
        self._db.flush()
        return attachment

    def search(
        self, organization_id: int, query: str
    ) -> list[tuple[str, int, str, str, int | None]]:
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        hits: list[tuple[str, int, str, str, int | None]] = []
        experiments = self._db.scalars(
            select(Experiment).where(
                Experiment.organization_id == organization_id,
                (Experiment.name.ilike(pattern, escape="\\"))
                | select(RecordTag.id)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == "experiment",
                    RecordTag.entity_id == Experiment.id,
                    RecordTag.tag.ilike(pattern, escape="\\"),
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
                (NotebookEntry.title.ilike(pattern, escape="\\"))
                | (NotebookEntry.content.ilike(pattern, escape="\\"))
                | select(RecordTag.id)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == "entry",
                    RecordTag.entity_id == NotebookEntry.id,
                    RecordTag.tag.ilike(pattern, escape="\\"),
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
                (InventoryItem.name.ilike(pattern, escape="\\"))
                | (InventoryItem.catalog_number.ilike(pattern, escape="\\"))
                | (InventoryItem.lot_number.ilike(pattern, escape="\\"))
                | select(RecordTag.id)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == "inventory",
                    RecordTag.entity_id == InventoryItem.id,
                    RecordTag.tag.ilike(pattern, escape="\\"),
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
                (Sample.name.ilike(pattern, escape="\\"))
                | (Sample.external_id.ilike(pattern, escape="\\"))
                | (Sample.sample_type.ilike(pattern, escape="\\"))
                | select(RecordTag.id)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == "sample",
                    RecordTag.entity_id == Sample.id,
                    RecordTag.tag.ilike(pattern, escape="\\"),
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
                (EquipmentResource.name.ilike(pattern, escape="\\"))
                | (EquipmentResource.location.ilike(pattern, escape="\\"))
                | (EquipmentResource.category.ilike(pattern, escape="\\"))
                | select(RecordTag.id)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == "equipment",
                    RecordTag.entity_id == EquipmentResource.id,
                    RecordTag.tag.ilike(pattern, escape="\\"),
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
                (NotebookTemplate.name.ilike(pattern, escape="\\"))
                | (NotebookTemplate.description.ilike(pattern, escape="\\"))
                | select(RecordTag.id)
                .where(
                    RecordTag.organization_id == organization_id,
                    RecordTag.entity_type == "template",
                    RecordTag.entity_id == NotebookTemplate.id,
                    RecordTag.tag.ilike(pattern, escape="\\"),
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
