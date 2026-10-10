import hashlib
import re
from decimal import Decimal
from datetime import timezone

from sqlalchemy.orm import Session

from eln_common.errors import EntityNotFoundError, InvalidInputError
from eln_common.outbox import enqueue_event

from .models import (
    EntryAttachment,
    EntryRevision,
    EquipmentBooking,
    EquipmentResource,
    Experiment,
    InventoryItem,
    NotebookEntry,
    NotebookTemplate,
    Sample,
    StockMovement,
)
from .attachment_storage import AttachmentStorage
from .repository import NotebookRepository


class NotebookService:
    MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024

    def __init__(
        self,
        repository: NotebookRepository,
        db: Session,
        attachment_storage: AttachmentStorage | None = None,
    ):
        self._repository = repository
        self._db = db
        self._attachment_storage = attachment_storage or AttachmentStorage()

    def list_experiments(
        self, organization_id: int, project_id: int
    ) -> list[Experiment]:
        return self._repository.list_experiments(organization_id, project_id)

    def get_experiment(self, organization_id: int, experiment_id: int) -> Experiment:
        experiment = self._repository.get_experiment(organization_id, experiment_id)
        if experiment is None:
            raise EntityNotFoundError("Experiment not found.")
        return experiment

    def create_experiment(
        self, organization_id: int, project_id: int, name: str, description: str
    ) -> Experiment:
        normalized_name = name.strip()
        if not normalized_name:
            raise InvalidInputError("Experiment name cannot be blank.")
        experiment = self._repository.add_experiment(
            Experiment(
                organization_id=organization_id,
                project_id=project_id,
                name=normalized_name,
                description=description.strip(),
            )
        )
        enqueue_event(
            self._db,
            source_service="notebook",
            action="created",
            entity_type="experiment",
            entity_id=experiment.id,
            organization_id=organization_id,
            details={"name": experiment.name, "project_id": str(project_id)},
        )
        self._db.commit()
        self._db.refresh(experiment)
        return experiment

    def list_entries(
        self, organization_id: int, experiment_id: int
    ) -> list[NotebookEntry]:
        self._require_experiment(organization_id, experiment_id)
        return self._repository.list_entries(organization_id, experiment_id)

    def get_entry(self, organization_id: int, entry_id: int) -> NotebookEntry:
        entry = self._repository.get_entry(organization_id, entry_id)
        if entry is None:
            raise EntityNotFoundError("Notebook entry not found.")
        return entry

    def create_entry(
        self, organization_id: int, experiment_id: int, title: str, content: str
    ) -> NotebookEntry:
        experiment = self._require_experiment(organization_id, experiment_id)
        normalized_title = title.strip()
        if not normalized_title:
            raise InvalidInputError("Entry title cannot be blank.")
        entry = self._repository.add_entry(
            NotebookEntry(
                organization_id=organization_id,
                experiment_id=experiment_id,
                title=normalized_title,
                content=content,
            )
        )
        enqueue_event(
            self._db,
            source_service="notebook",
            action="created",
            entity_type="notebook_entry",
            entity_id=entry.id,
            organization_id=organization_id,
            details={
                "title": entry.title,
                "project_id": str(experiment.project_id),
            },
        )
        self._db.commit()
        self._db.refresh(entry)
        return entry

    def update_entry(
        self,
        organization_id: int,
        entry_id: int,
        user_id: int,
        title: str,
        content: str,
    ) -> NotebookEntry:
        entry = self._repository.get_entry(organization_id, entry_id)
        if entry is None:
            raise EntityNotFoundError("Notebook entry not found.")
        experiment = self._require_experiment(organization_id, entry.experiment_id)
        normalized_title = title.strip()
        if not normalized_title:
            raise InvalidInputError("Entry title cannot be blank.")
        self._repository.add_revision(
            EntryRevision(
                organization_id=organization_id,
                entry_id=entry.id,
                revision_number=self._repository.next_revision_number(
                    organization_id, entry.id
                ),
                title=entry.title,
                content=entry.content,
                changed_by_user_id=user_id,
            )
        )
        entry.title = normalized_title
        entry.content = content
        self._db.flush()
        enqueue_event(
            self._db,
            source_service="notebook",
            action="updated",
            entity_type="notebook_entry",
            entity_id=entry.id,
            organization_id=organization_id,
            details={
                "title": entry.title,
                "project_id": str(experiment.project_id),
                "changed_by_user_id": str(user_id),
            },
        )
        self._db.commit()
        self._db.refresh(entry)
        return entry

    def list_entry_revisions(
        self, organization_id: int, entry_id: int
    ) -> list[EntryRevision]:
        self.get_entry(organization_id, entry_id)
        return self._repository.list_revisions(organization_id, entry_id)

    def restore_entry_revision(
        self,
        organization_id: int,
        entry_id: int,
        revision_id: int,
        user_id: int,
    ) -> NotebookEntry:
        revision = self._repository.get_revision(
            organization_id, entry_id, revision_id
        )
        if revision is None:
            raise EntityNotFoundError("Notebook entry revision not found.")
        return self.update_entry(
            organization_id,
            entry_id,
            user_id,
            revision.title,
            revision.content,
        )

    def _require_experiment(
        self, organization_id: int, experiment_id: int
    ) -> Experiment:
        experiment = self._repository.get_experiment(organization_id, experiment_id)
        if experiment is None:
            raise EntityNotFoundError("Experiment not found.")
        return experiment

    def list_inventory(self, organization_id: int) -> list[InventoryItem]:
        return self._repository.list_inventory(organization_id)

    def create_inventory_item(
        self, organization_id: int, user_id: int, values: dict
    ) -> InventoryItem:
        name = values["name"].strip()
        unit = values["unit"].strip()
        if not name or not unit:
            raise InvalidInputError("Inventory item name and unit cannot be blank.")
        item = self._repository.add_inventory_item(
            InventoryItem(
                organization_id=organization_id,
                **{**values, "name": name, "unit": unit},
            )
        )
        if item.quantity > 0:
            self._repository.add_stock_movement(
                StockMovement(
                    organization_id=organization_id,
                    item_id=item.id,
                    changed_by_user_id=user_id,
                    quantity_delta=item.quantity,
                    resulting_quantity=item.quantity,
                    reason="Initial stock",
                )
            )
        enqueue_event(
            self._db,
            source_service="notebook",
            action="created",
            entity_type="inventory_item",
            entity_id=item.id,
            organization_id=organization_id,
            details={"name": item.name, "category": item.category},
        )
        self._db.commit()
        self._db.refresh(item)
        return item

    def adjust_stock(
        self,
        organization_id: int,
        item_id: int,
        user_id: int,
        quantity_delta: Decimal,
        reason: str,
    ) -> StockMovement:
        item = self._repository.get_inventory_item(organization_id, item_id)
        if item is None:
            raise EntityNotFoundError("Inventory item not found.")
        normalized_reason = reason.strip()
        if not normalized_reason or quantity_delta == 0:
            raise InvalidInputError("A non-zero quantity change and reason are required.")
        changed = self._repository.change_inventory_quantity(
            organization_id, item_id, quantity_delta
        )
        if not changed:
            self._db.refresh(item)
            if item.quantity + quantity_delta < 0:
                raise InvalidInputError("Stock adjustment cannot make inventory negative.")
            raise EntityNotFoundError("Inventory item not found.")
        self._db.refresh(item)
        next_quantity = item.quantity
        if next_quantity < 0:
            raise InvalidInputError("Stock adjustment cannot make inventory negative.")
        movement = self._repository.add_stock_movement(
            StockMovement(
                organization_id=organization_id,
                item_id=item.id,
                changed_by_user_id=user_id,
                quantity_delta=quantity_delta,
                resulting_quantity=next_quantity,
                reason=normalized_reason,
            )
        )
        enqueue_event(
            self._db,
            source_service="notebook",
            action="stock_adjusted",
            entity_type="inventory_item",
            entity_id=item.id,
            organization_id=organization_id,
            details={
                "name": item.name,
                "quantity_delta": str(quantity_delta),
                "resulting_quantity": str(next_quantity),
                "changed_by_user_id": str(user_id),
            },
        )
        self._db.commit()
        self._db.refresh(movement)
        return movement

    def list_stock_movements(
        self, organization_id: int, item_id: int
    ) -> list[StockMovement]:
        if self._repository.get_inventory_item(organization_id, item_id) is None:
            raise EntityNotFoundError("Inventory item not found.")
        return self._repository.list_stock_movements(organization_id, item_id)

    def list_samples(self, organization_id: int) -> list[Sample]:
        return self._repository.list_samples(organization_id)

    def create_sample(
        self, organization_id: int, user_id: int, values: dict
    ) -> Sample:
        name = values["name"].strip()
        sample_type = values["sample_type"].strip()
        if not name or not sample_type:
            raise InvalidInputError("Sample name and type cannot be blank.")
        parent_id = values.get("parent_sample_id")
        if parent_id is not None and self._repository.get_sample(
            organization_id, parent_id
        ) is None:
            raise EntityNotFoundError("Parent sample not found.")
        sample = self._repository.add_sample(
            Sample(
                organization_id=organization_id,
                created_by_user_id=user_id,
                **{**values, "name": name, "sample_type": sample_type},
            )
        )
        enqueue_event(
            self._db,
            source_service="notebook",
            action="created",
            entity_type="sample",
            entity_id=sample.id,
            organization_id=organization_id,
            details={"name": sample.name, "sample_type": sample.sample_type},
        )
        self._db.commit()
        self._db.refresh(sample)
        return sample

    def list_templates(self, organization_id: int) -> list[NotebookTemplate]:
        return self._repository.list_templates(organization_id)

    def search(self, organization_id: int, query: str) -> list[dict]:
        normalized_query = query.strip()
        if len(normalized_query) < 2:
            raise InvalidInputError("Search query must contain at least two characters.")
        if len(normalized_query) > 100:
            raise InvalidInputError("Search query cannot exceed 100 characters.")
        return [
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "title": title,
                "detail": detail,
                "project_id": project_id,
            }
            for entity_type, entity_id, title, detail, project_id
            in self._repository.search(organization_id, normalized_query)
        ]

    def create_template(
        self, organization_id: int, user_id: int, values: dict
    ) -> NotebookTemplate:
        name = values["name"].strip()
        if not name:
            raise InvalidInputError("Template name cannot be blank.")
        template = self._repository.add_template(
            NotebookTemplate(
                organization_id=organization_id,
                created_by_user_id=user_id,
                **{**values, "name": name},
            )
        )
        self._db.commit()
        self._db.refresh(template)
        return template

    def update_template(
        self, organization_id: int, template_id: int, user_id: int, values: dict
    ) -> NotebookTemplate:
        template = self._repository.get_template(organization_id, template_id)
        if template is None:
            raise EntityNotFoundError("Notebook template not found.")
        if template.created_by_user_id != user_id:
            raise EntityNotFoundError("Notebook template not found.")
        name = values["name"].strip()
        if not name:
            raise InvalidInputError("Template name cannot be blank.")
        template.name = name
        template.template_kind = values["template_kind"]
        template.description = values["description"].strip()
        template.sections = values["sections"]
        self._db.commit()
        self._db.refresh(template)
        return template

    def apply_entry_template(
        self,
        organization_id: int,
        entry_id: int,
        template_id: int,
        user_id: int,
    ) -> NotebookEntry:
        entry = self.get_entry(organization_id, entry_id)
        template = self._repository.get_template(organization_id, template_id)
        if template is None:
            raise EntityNotFoundError("Notebook template not found.")
        if template.template_kind != "entry":
            raise InvalidInputError("Only entry templates can be applied to an entry.")
        self._repository.add_revision(
            EntryRevision(
                organization_id=organization_id,
                entry_id=entry.id,
                revision_number=self._repository.next_revision_number(
                    organization_id, entry.id
                ),
                title=entry.title,
                content=entry.content,
                changed_by_user_id=user_id,
            )
        )
        section_text = "\n\n".join(
            f"## {section['title']}\n\n{section.get('instructions', '')}".rstrip()
            for section in template.sections
        )
        entry.title = template.name
        entry.content = section_text
        self._db.flush()
        enqueue_event(
            self._db,
            source_service="notebook",
            action="template_applied",
            entity_type="notebook_entry",
            entity_id=entry.id,
            organization_id=organization_id,
            details={"title": entry.title, "template_id": str(template.id)},
        )
        self._db.commit()
        self._db.refresh(entry)
        return entry

    def create_experiment_from_protocol(
        self,
        organization_id: int,
        project_id: int,
        template_id: int,
    ) -> tuple[Experiment, NotebookEntry]:
        template = self._repository.get_template(organization_id, template_id)
        if template is None:
            raise EntityNotFoundError("Notebook template not found.")
        if template.template_kind != "protocol":
            raise InvalidInputError("Selected template is not a protocol.")
        experiment = self._repository.add_experiment(
            Experiment(
                organization_id=organization_id,
                project_id=project_id,
                name=template.name,
                description=template.description,
            )
        )
        content = "\n\n".join(
            f"## {section['title']}\n\n{section.get('instructions', '')}".rstrip()
            for section in template.sections
        )
        entry = self._repository.add_entry(
            NotebookEntry(
                organization_id=organization_id,
                experiment_id=experiment.id,
                title=f"{template.name} — Protocol",
                content=content,
            )
        )
        enqueue_event(
            self._db,
            source_service="notebook",
            action="protocol_started",
            entity_type="experiment",
            entity_id=experiment.id,
            organization_id=organization_id,
            details={
                "name": experiment.name,
                "project_id": str(project_id),
                "template_id": str(template.id),
            },
        )
        self._db.commit()
        self._db.refresh(experiment)
        self._db.refresh(entry)
        return experiment, entry

    def list_attachments(
        self, organization_id: int, entry_id: int
    ) -> list[EntryAttachment]:
        self.get_entry(organization_id, entry_id)
        return self._repository.list_attachments(organization_id, entry_id)

    def add_attachment(
        self,
        organization_id: int,
        entry_id: int,
        user_id: int,
        filename: str,
        media_type: str,
        content: bytes,
    ) -> EntryAttachment:
        self.get_entry(organization_id, entry_id)
        safe_name = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
        if (
            not safe_name
            or len(safe_name) > 255
            or any(ord(char) < 32 or ord(char) == 127 for char in safe_name)
        ):
            raise InvalidInputError("Attachment filename is invalid.")
        if not content or len(content) > self.MAX_ATTACHMENT_BYTES:
            raise InvalidInputError("Attachment must be between 1 byte and 25 MiB.")
        if len(media_type) > 160 or re.search(r"[\r\n]", media_type):
            media_type = "application/octet-stream"
        storage_key, _ = self._attachment_storage.save(content)
        attachment = EntryAttachment(
            organization_id=organization_id,
            entry_id=entry_id,
            storage_key=storage_key,
            original_filename=safe_name,
            media_type=media_type or "application/octet-stream",
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            uploaded_by_user_id=user_id,
        )
        try:
            self._repository.add_attachment(attachment)
            enqueue_event(
                self._db,
                source_service="notebook",
                action="attachment_added",
                entity_type="notebook_entry",
                entity_id=entry_id,
                organization_id=organization_id,
                details={
                    "filename": safe_name,
                    "size_bytes": str(len(content)),
                    "uploaded_by_user_id": str(user_id),
                },
            )
            self._db.commit()
            self._db.refresh(attachment)
            return attachment
        except Exception:
            self._db.rollback()
            self._attachment_storage.remove(storage_key)
            raise

    def get_attachment(
        self, organization_id: int, attachment_id: int
    ) -> EntryAttachment:
        attachment = self._repository.get_attachment(organization_id, attachment_id)
        if attachment is None:
            raise EntityNotFoundError("Attachment not found.")
        return attachment

    def attachment_path(self, attachment: EntryAttachment):
        return self._attachment_storage.path_for(attachment.storage_key)

    def list_equipment(self, organization_id: int) -> list[EquipmentResource]:
        return self._repository.list_equipment(organization_id)

    def create_equipment(
        self, organization_id: int, user_id: int, values: dict
    ) -> EquipmentResource:
        name = values["name"].strip()
        if not name:
            raise InvalidInputError("Equipment name cannot be blank.")
        equipment = self._repository.add_equipment(
            EquipmentResource(
                organization_id=organization_id,
                created_by_user_id=user_id,
                **{**values, "name": name},
            )
        )
        self._db.commit()
        self._db.refresh(equipment)
        return equipment

    def list_bookings(self, organization_id: int) -> list[EquipmentBooking]:
        return self._repository.list_bookings(organization_id)

    def create_booking(
        self,
        organization_id: int,
        equipment_id: int,
        user_id: int,
        values: dict,
    ) -> EquipmentBooking:
        equipment = self._repository.get_equipment(
            organization_id, equipment_id, lock=True
        )
        if equipment is None:
            raise EntityNotFoundError("Equipment not found.")
        starts_at = values["starts_at"].astimezone(timezone.utc)
        ends_at = values["ends_at"].astimezone(timezone.utc)
        if self._repository.has_booking_conflict(
            organization_id, equipment_id, starts_at, ends_at
        ):
            raise InvalidInputError("Equipment is already booked during that time.")
        booking = self._repository.add_booking(
            EquipmentBooking(
                organization_id=organization_id,
                equipment_id=equipment_id,
                booked_by_user_id=user_id,
                **{**values, "starts_at": starts_at, "ends_at": ends_at},
            )
        )
        enqueue_event(
            self._db,
            source_service="notebook",
            action="equipment_booked",
            entity_type="equipment_booking",
            entity_id=booking.id,
            organization_id=organization_id,
            details={
                "equipment_id": str(equipment_id),
                "booked_by_user_id": str(user_id),
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
            },
        )
        self._db.commit()
        self._db.refresh(booking)
        return booking

    def cancel_booking(
        self, organization_id: int, booking_id: int, user_id: int, is_admin: bool
    ) -> EquipmentBooking:
        booking = self._repository.get_booking(organization_id, booking_id)
        if booking is None:
            raise EntityNotFoundError("Equipment booking not found.")
        if booking.booked_by_user_id != user_id and not is_admin:
            raise EntityNotFoundError("Equipment booking not found.")
        if booking.status != "reserved":
            raise InvalidInputError("Only active bookings can be cancelled.")
        booking.status = "cancelled"
        enqueue_event(
            self._db,
            source_service="notebook",
            action="equipment_booking_cancelled",
            entity_type="equipment_booking",
            entity_id=booking.id,
            organization_id=organization_id,
            details={"cancelled_by_user_id": str(user_id)},
        )
        self._db.commit()
        self._db.refresh(booking)
        return booking
