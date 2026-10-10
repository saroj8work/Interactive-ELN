from decimal import Decimal
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .models import (
    Experiment,
    EntryAttachment,
    EntryRevision,
    EquipmentBooking,
    EquipmentResource,
    InventoryItem,
    NotebookEntry,
    NotebookTemplate,
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
                .where(InventoryItem.organization_id == organization_id)
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
                .where(Sample.organization_id == organization_id)
                .order_by(Sample.created_at.desc(), Sample.id.desc())
            )
        )

    def get_sample(self, organization_id: int, sample_id: int) -> Sample | None:
        return self._db.scalar(
            select(Sample).where(
                Sample.organization_id == organization_id, Sample.id == sample_id
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
                .where(NotebookTemplate.organization_id == organization_id)
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
                .where(EquipmentResource.organization_id == organization_id)
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
                Experiment.name.ilike(pattern, escape="\\"),
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
                | (NotebookEntry.content.ilike(pattern, escape="\\")),
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
                (InventoryItem.name.ilike(pattern, escape="\\"))
                | (InventoryItem.catalog_number.ilike(pattern, escape="\\"))
                | (InventoryItem.lot_number.ilike(pattern, escape="\\")),
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
                (Sample.name.ilike(pattern, escape="\\"))
                | (Sample.external_id.ilike(pattern, escape="\\"))
                | (Sample.sample_type.ilike(pattern, escape="\\")),
            )
            .limit(100)
        )
        hits.extend(
            ("sample", sample.id, sample.name, sample.external_id, sample.project_id)
            for sample in samples
        )
        templates = self._db.scalars(
            select(NotebookTemplate)
            .where(
                NotebookTemplate.organization_id == organization_id,
                (NotebookTemplate.name.ilike(pattern, escape="\\"))
                | (NotebookTemplate.description.ilike(pattern, escape="\\")),
            )
            .limit(100)
        )
        hits.extend(
            ("template", template.id, template.name, template.description, None)
            for template in templates
        )
        return hits
