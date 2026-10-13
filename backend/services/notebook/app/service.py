import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session
from rfc3161ng import RemoteTimestamper, TimestampingError, get_timestamp

from eln_common.errors import EntityNotFoundError, InvalidInputError
from eln_common.outbox import enqueue_event

from eln_common.errors import ServiceUnavailableError

from .models import (
    EntryAttachment,
    EntryRevision,
    EntryTimestamp,
    AuditEvent,
    EquipmentBooking,
    EquipmentResource,
    Experiment,
    InventoryItem,
    LabTask,
    NotebookEntry,
    NotebookTemplate,
    RecordSignature,
    Sample,
    StockMovement,
    StorageLocation,
    WorkflowExecution,
    WorkflowRule,
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

    def update_experiment_status(
        self,
        organization_id: int,
        experiment_id: int,
        user_id: int,
        status: str,
    ) -> Experiment:
        experiment = self.get_experiment(organization_id, experiment_id)
        if status not in {"in_progress", "completed", "archived"}:
            raise InvalidInputError("Experiment status is invalid.")
        if experiment.status == status:
            return experiment
        previous_status = experiment.status
        transition_id = str(uuid.uuid4())
        experiment.status = status
        rules = list(
            self._db.scalars(
                select(WorkflowRule).where(
                    WorkflowRule.organization_id == organization_id,
                    WorkflowRule.project_id == experiment.project_id,
                    WorkflowRule.enabled.is_(True),
                    WorkflowRule.to_status == status,
                    (WorkflowRule.from_status == previous_status)
                    | (WorkflowRule.from_status.is_(None)),
                )
            )
        )
        for rule in rules:
            now = datetime.now(timezone.utc)
            task = LabTask(
                organization_id=organization_id,
                project_id=experiment.project_id,
                experiment_id=experiment.id,
                assigned_to_user_id=None,
                created_by_user_id=user_id,
                title=rule.task_title,
                description=rule.task_description,
                priority=rule.task_priority,
                due_at=(
                    now + timedelta(days=rule.due_days)
                    if rule.due_days is not None
                    else None
                ),
            )
            self._db.add(task)
            self._db.flush()
            self._db.add(
                WorkflowExecution(
                    organization_id=organization_id,
                    rule_id=rule.id,
                    transition_id=transition_id,
                    experiment_id=experiment.id,
                    task_id=task.id,
                )
            )
            enqueue_event(
                self._db,
                source_service="notebook",
                action="workflow_task_created",
                entity_type="lab_task",
                entity_id=task.id,
                organization_id=organization_id,
                details={
                    "rule_id": str(rule.id),
                    "experiment_id": str(experiment.id),
                    "transition_id": transition_id,
                },
            )
        enqueue_event(
            self._db,
            source_service="notebook",
            action="status_changed",
            entity_type="experiment",
            entity_id=experiment.id,
            organization_id=organization_id,
            details={
                "project_id": str(experiment.project_id),
                "status": status,
                "previous_status": previous_status,
                "changed_by_user_id": str(user_id),
                "transition_id": transition_id,
            },
        )
        self._db.commit()
        self._db.refresh(experiment)
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

    def create_task(
        self, organization_id: int, user_id: int, values: dict
    ) -> LabTask:
        title = values["title"].strip()
        if not title:
            raise InvalidInputError("Task title cannot be blank.")
        experiment_id = values.get("experiment_id")
        if experiment_id is not None:
            experiment = self._repository.get_experiment(
                organization_id, experiment_id
            )
            if experiment is None or experiment.project_id != values["project_id"]:
                raise EntityNotFoundError("Experiment not found in this project.")
        task = self._repository.add_task(
            LabTask(
                organization_id=organization_id,
                created_by_user_id=user_id,
                **{**values, "title": title},
            )
        )
        enqueue_event(
            self._db,
            source_service="notebook",
            action="task_created",
            entity_type="lab_task",
            entity_id=task.id,
            organization_id=organization_id,
            details={
                "project_id": str(task.project_id),
                "title": task.title,
                "created_by_user_id": str(user_id),
            },
        )
        self._db.commit()
        self._db.refresh(task)
        return task

    def list_workflow_rules(
        self, organization_id: int, project_id: int
    ) -> list[WorkflowRule]:
        return list(
            self._db.scalars(
                select(WorkflowRule)
                .where(
                    WorkflowRule.organization_id == organization_id,
                    WorkflowRule.project_id == project_id,
                )
                .order_by(WorkflowRule.created_at.desc())
            )
        )

    def create_workflow_rule(
        self, organization_id: int, user_id: int, values: dict
    ) -> WorkflowRule:
        if values.get("from_status") == values["to_status"]:
            raise InvalidInputError("Workflow transition statuses must differ.")
        project_id = values["project_id"]
        rule = WorkflowRule(
            organization_id=organization_id,
            created_by_user_id=user_id,
            **values,
        )
        self._db.add(rule)
        self._db.commit()
        self._db.refresh(rule)
        return rule

    def list_storage_locations(
        self, organization_id: int, active_only: bool = True
    ) -> list[StorageLocation]:
        query = select(StorageLocation).where(
            StorageLocation.organization_id == organization_id
        )
        if active_only:
            query = query.where(StorageLocation.status == "active")
        return list(self._db.scalars(query.order_by(StorageLocation.code)))

    def create_storage_location(
        self, organization_id: int, user_id: int, values: dict
    ) -> StorageLocation:
        code = values["code"].strip()
        name = values["name"].strip()
        if not code or not name:
            raise InvalidInputError("Location code and name cannot be blank.")
        parent_id = values.get("parent_id")
        if parent_id is not None:
            parent = self._db.scalar(
                select(StorageLocation).where(
                    StorageLocation.id == parent_id,
                    StorageLocation.organization_id == organization_id,
                    StorageLocation.status == "active",
                )
            )
            if parent is None:
                raise EntityNotFoundError("Parent storage location not found.")
        location = StorageLocation(
            organization_id=organization_id,
            created_by_user_id=user_id,
            **{**values, "code": code, "name": name},
        )
        self._db.add(location)
        self._db.commit()
        self._db.refresh(location)
        return location

    def create_entry_timestamp(
        self, organization_id: int, entry_id: int, user_id: int
    ) -> EntryTimestamp:
        tsa_url = os.getenv("ELN_TSA_URL", "").strip()
        certificate_path = os.getenv("ELN_TSA_CERTIFICATE_FILE", "").strip()
        if not tsa_url or not certificate_path:
            raise ServiceUnavailableError(
                "RFC 3161 timestamping is not configured. Set ELN_TSA_URL and "
                "ELN_TSA_CERTIFICATE_FILE to the trusted TSA endpoint and pinned "
                "signer certificate."
            )
        parsed_url = urlparse(tsa_url)
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            raise InvalidInputError("The configured TSA endpoint must use HTTPS.")
        try:
            certificate = Path(certificate_path).read_bytes()
        except OSError as error:
            raise ServiceUnavailableError(
                "The configured TSA signer certificate could not be read."
            ) from error
        entry = self.get_entry(organization_id, entry_id)
        snapshot = json.dumps(
            {
                "entry_id": entry.id,
                "experiment_id": entry.experiment_id,
                "organization_id": entry.organization_id,
                "title": entry.title,
                "content": entry.content,
                "created_at": entry.created_at.isoformat(),
                "updated_at": entry.updated_at.isoformat(),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        record_hash = hashlib.sha256(snapshot).hexdigest()
        try:
            timestamper = RemoteTimestamper(
                tsa_url,
                certificate=certificate,
                hashname="sha256",
                timeout=10,
            )
            token = timestamper.timestamp(data=snapshot)
        except (TimestampingError, ValueError, OSError) as error:
            raise ServiceUnavailableError(
                "The TSA request failed or its response could not be verified "
                "against the configured signer certificate."
            ) from error
        timestamp = get_timestamp(token)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)
        record = EntryTimestamp(
            organization_id=organization_id,
            entry_id=entry.id,
            requested_by_user_id=user_id,
            tsa_url=tsa_url,
            record_sha256=record_hash,
            snapshot_json=snapshot.decode("utf-8"),
            token_der=token,
            tsa_time=timestamp,
        )
        self._db.add(record)
        self._db.commit()
        self._db.refresh(record)
        return record

    def list_entry_timestamps(
        self, organization_id: int, entry_id: int
    ) -> list[EntryTimestamp]:
        self.get_entry(organization_id, entry_id)
        return list(
            self._db.scalars(
                select(EntryTimestamp)
                .where(
                    EntryTimestamp.organization_id == organization_id,
                    EntryTimestamp.entry_id == entry_id,
                )
                .order_by(EntryTimestamp.tsa_time.desc())
            )
        )

    def get_entry_timestamp(
        self, organization_id: int, entry_id: int, timestamp_id: int
    ) -> EntryTimestamp:
        timestamp = self._db.scalar(
            select(EntryTimestamp).where(
                EntryTimestamp.organization_id == organization_id,
                EntryTimestamp.entry_id == entry_id,
                EntryTimestamp.id == timestamp_id,
            )
        )
        if timestamp is None:
            raise EntityNotFoundError("Entry timestamp proof not found.")
        return timestamp

    def list_tasks(self, organization_id: int, project_id: int) -> list[LabTask]:
        return self._repository.list_tasks(organization_id, project_id)

    def get_task(self, organization_id: int, task_id: int) -> LabTask:
        task = self._repository.get_task(organization_id, task_id)
        if task is None:
            raise EntityNotFoundError("Task not found.")
        return task

    def update_task_status(
        self, organization_id: int, task_id: int, user_id: int, status: str
    ) -> LabTask:
        task = self._repository.get_task(organization_id, task_id)
        if task is None:
            raise EntityNotFoundError("Task not found.")
        if status not in {"open", "in_progress", "blocked", "completed", "cancelled"}:
            raise InvalidInputError("Task status is invalid.")
        if task.status != status:
            task.status = status
            enqueue_event(
                self._db,
                source_service="notebook",
                action="task_status_changed",
                entity_type="lab_task",
                entity_id=task.id,
                organization_id=organization_id,
                details={
                    "project_id": str(task.project_id),
                    "status": status,
                    "changed_by_user_id": str(user_id),
                },
            )
            self._db.commit()
            self._db.refresh(task)
        return task

    def update_resource_status(
        self,
        organization_id: int,
        entity_type: str,
        entity_id: int,
        user_id: int,
        status: str,
    ):
        if status not in {"active", "archived"}:
            raise InvalidInputError("Resource status is invalid.")
        resource_map = {
            "inventory": (InventoryItem, "Inventory item not found."),
            "sample": (Sample, "Sample not found."),
            "equipment": (EquipmentResource, "Equipment not found."),
            "template": (NotebookTemplate, "Notebook template not found."),
        }
        resource = resource_map.get(entity_type)
        if resource is None:
            raise InvalidInputError("Unsupported resource type.")
        model, not_found_message = resource
        record = self._db.get(model, entity_id)
        if record is None or record.organization_id != organization_id:
            raise EntityNotFoundError(not_found_message)
        if (
            entity_type == "equipment"
            and status == "archived"
            and self._repository.has_active_equipment_bookings(
                organization_id, entity_id
            )
        ):
            raise InvalidInputError(
                "Equipment with current or upcoming reservations cannot be archived."
            )
        if record.status != status:
            record.status = status
            enqueue_event(
                self._db,
                source_service="notebook",
                action=f"{entity_type}_{status}",
                entity_type=entity_type,
                entity_id=entity_id,
                organization_id=organization_id,
                details={"changed_by_user_id": str(user_id)},
            )
            self._db.commit()
            self._db.refresh(record)
        return record

    def get_resource(self, organization_id: int, entity_type: str, entity_id: int):
        messages = {
            "inventory": "Inventory item not found.",
            "sample": "Sample not found.",
            "equipment": "Equipment not found.",
            "template": "Notebook template not found.",
        }
        if entity_type not in messages:
            raise InvalidInputError("Unsupported resource type.")
        resource = self._repository.get_resource(
            organization_id, entity_type, entity_id
        )
        if resource is None:
            raise EntityNotFoundError(messages[entity_type])
        return resource

    def create_signature(
        self,
        organization_id: int,
        user_id: int,
        entry_id: int,
        meaning: str,
        comment: str,
    ) -> RecordSignature:
        key = os.getenv("ELN_AUDIT_HMAC_KEY", "")
        if len(key.encode("utf-8")) < 32:
            raise ServiceUnavailableError(
                "Audit signing is unavailable; configure ELN_AUDIT_HMAC_KEY "
                "with at least 32 bytes."
            )
        entry = self.get_entry(organization_id, entry_id)
        timestamp = datetime.now(timezone.utc)
        record_payload = json.dumps(
            {
                "entry_id": entry.id,
                "title": entry.title,
                "content": entry.content,
                "updated_at": entry.updated_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        record_digest = hashlib.sha256(record_payload).hexdigest()
        head = self._repository.get_audit_head(organization_id)
        previous_hash = head.event_hash if head else "0" * 64
        signature_payload = {
            "organization_id": organization_id,
            "entity_type": "entry",
            "entity_id": entry_id,
            "signed_by_user_id": user_id,
            "meaning": meaning,
            "comment": comment.strip(),
            "record_sha256": record_digest,
            "previous_hash": previous_hash,
            "created_at": timestamp,
        }
        signature_hash_payload = {
            **signature_payload,
            "created_at": timestamp.isoformat(),
        }
        canonical_signature = json.dumps(
            signature_hash_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        event_hash = hmac.new(
            key.encode("utf-8"), canonical_signature.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        signature = self._repository.add_signature(
            RecordSignature(
                **signature_payload,
                event_hash=event_hash,
            )
        )
        serialized_signature_payload = {
            **signature_hash_payload,
        }
        audit_payload = json.dumps(
            {"signature_id": signature.id, **serialized_signature_payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        audit_hash = hmac.new(
            key.encode("utf-8"),
            json.dumps(
                {
                    "organization_id": organization_id,
                    "actor_user_id": user_id,
                    "action": "record_signed",
                    "entity_type": "entry",
                    "entity_id": entry_id,
                    "payload_json": audit_payload,
                    "previous_hash": previous_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self._repository.add_audit_event(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=user_id,
                action="record_signed",
                entity_type="entry",
                entity_id=entry_id,
                payload_json=audit_payload,
                previous_hash=previous_hash,
                event_hash=audit_hash,
                created_at=timestamp,
            )
        )
        self._db.commit()
        self._db.refresh(signature)
        return signature

    def list_signatures(
        self, organization_id: int, entry_id: int
    ) -> list[RecordSignature]:
        self.get_entry(organization_id, entry_id)
        return self._repository.list_signatures(organization_id, "entry", entry_id)

    def verify_audit_chain(self, organization_id: int) -> dict[str, int | bool]:
        key = os.getenv("ELN_AUDIT_HMAC_KEY", "")
        if len(key.encode("utf-8")) < 32:
            raise ServiceUnavailableError(
                "Audit verification is unavailable; configure ELN_AUDIT_HMAC_KEY "
                "with at least 32 bytes."
            )
        events = self._repository.list_audit_events(organization_id)
        previous_hash = "0" * 64
        for event in events:
            if event.previous_hash != previous_hash:
                return {
                    "organization_id": organization_id,
                    "valid": False,
                    "checked_events": len(events),
                }
            if event.action == "record_signed":
                try:
                    signed_payload = json.loads(event.payload_json)
                    signature_id = int(signed_payload.pop("signature_id"))
                except (ValueError, TypeError, json.JSONDecodeError, KeyError):
                    return {
                        "organization_id": organization_id,
                        "valid": False,
                        "checked_events": len(events),
                    }
                signature = self._repository.get_signature(
                    organization_id, signature_id
                )
                signature_canonical = json.dumps(
                    signed_payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                expected_signature_hash = hmac.new(
                    key.encode("utf-8"),
                    signature_canonical.encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
                if (
                    signature is None
                    or not hmac.compare_digest(
                        expected_signature_hash, signature.event_hash
                    )
                    or signature.entity_id != event.entity_id
                    or signature.signed_by_user_id != event.actor_user_id
                    or signature.organization_id
                    != signed_payload.get("organization_id")
                    or signature.entity_type != signed_payload.get("entity_type")
                    or signature.meaning != signed_payload.get("meaning")
                    or signature.comment != signed_payload.get("comment")
                    or signature.record_sha256
                    != signed_payload.get("record_sha256")
                    or signature.previous_hash
                    != signed_payload.get("previous_hash")
                ):
                    return {
                        "organization_id": organization_id,
                        "valid": False,
                        "checked_events": len(events),
                    }
            payload = json.dumps(
                {
                    "organization_id": event.organization_id,
                    "actor_user_id": event.actor_user_id,
                    "action": event.action,
                    "entity_type": event.entity_type,
                    "entity_id": event.entity_id,
                    "payload_json": event.payload_json,
                    "previous_hash": event.previous_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            expected_hash = hmac.new(
                key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(expected_hash, event.event_hash):
                return {
                    "organization_id": organization_id,
                    "valid": False,
                    "checked_events": len(events),
                }
            previous_hash = event.event_hash
        return {
            "organization_id": organization_id,
            "valid": True,
            "checked_events": len(events),
        }

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

    def get_record_tags(
        self, organization_id: int, entity_type: str, entity_id: int
    ) -> dict:
        supported_types = {
            "experiment",
            "entry",
            "inventory",
            "sample",
            "equipment",
            "template",
        }
        if entity_type not in supported_types:
            raise InvalidInputError("Unsupported tagged record type.")
        exists, _ = self._repository.record_tag_target(
            organization_id, entity_type, entity_id
        )
        if not exists:
            raise EntityNotFoundError("Tagged record not found.")
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "tags": self._repository.list_record_tags(
                organization_id, entity_type, entity_id
            ),
        }

    def replace_record_tags(
        self,
        organization_id: int,
        entity_type: str,
        entity_id: int,
        user_id: int,
        tags: list[str],
    ) -> dict:
        if entity_type not in {
            "experiment",
            "entry",
            "inventory",
            "sample",
            "equipment",
            "template",
        }:
            raise InvalidInputError("Unsupported tagged record type.")
        exists, project_id = self._repository.record_tag_target(
            organization_id, entity_type, entity_id
        )
        if not exists:
            raise EntityNotFoundError("Tagged record not found.")
        normalized_tags = sorted({tag.strip().casefold() for tag in tags})
        if any(not tag or len(tag) > 40 for tag in normalized_tags):
            raise InvalidInputError("Tags must contain 1 to 40 characters.")
        self._repository.replace_record_tags(
            organization_id, entity_type, entity_id, user_id, normalized_tags
        )
        enqueue_event(
            self._db,
            source_service="notebook",
            action="tags_updated",
            entity_type=f"notebook_{entity_type}",
            entity_id=entity_id,
            organization_id=organization_id,
            details={
                "project_id": str(project_id),
                "tags": ",".join(normalized_tags),
                "changed_by_user_id": str(user_id),
            },
        )
        self._db.commit()
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "tags": self._repository.list_record_tags(
                organization_id, entity_type, entity_id
            ),
        }

    def list_project_record_tags(
        self, organization_id: int, project_id: int
    ) -> list[dict]:
        return [
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "tags": tags,
            }
            for (entity_type, entity_id), tags in self._repository.list_project_record_tags(
                organization_id, project_id
            ).items()
        ]

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

    def _location_label(
        self, organization_id: int, location_id: int | None, legacy_text: str
    ) -> str:
        if location_id is None:
            return legacy_text
        location = self._db.scalar(
            select(StorageLocation).where(
                StorageLocation.id == location_id,
                StorageLocation.organization_id == organization_id,
                StorageLocation.status == "active",
            )
        )
        if location is None:
            raise EntityNotFoundError("Active storage location not found.")
        return location.name

    def create_inventory_item(
        self, organization_id: int, user_id: int, values: dict
    ) -> InventoryItem:
        name = values["name"].strip()
        unit = values["unit"].strip()
        category = values["category"].strip()
        if not name or not unit or not category:
            raise InvalidInputError(
                "Inventory item name, category, and unit cannot be blank."
            )
        values["location"] = self._location_label(
            organization_id, values.get("location_id"), values.get("location", "")
        )
        item = self._repository.add_inventory_item(
            InventoryItem(
                organization_id=organization_id,
                **{**values, "name": name, "category": category, "unit": unit},
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
        if item.status != "active":
            raise InvalidInputError("Archived inventory items cannot be adjusted.")
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
        values["storage_location"] = self._location_label(
            organization_id,
            values.get("storage_location_id"),
            values.get("storage_location", ""),
        )
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
        if template.status != "active":
            raise InvalidInputError("Archived templates cannot be applied.")
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
        if template.status != "active":
            raise InvalidInputError("Archived templates cannot start protocols.")
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
        values["location"] = self._location_label(
            organization_id,
            values.get("storage_location_id"),
            values.get("location", ""),
        )
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
        if equipment.status != "active":
            raise InvalidInputError("Archived equipment cannot be booked.")
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
