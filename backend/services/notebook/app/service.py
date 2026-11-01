import calendar
import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from rfc3161ng import RemoteTimestamper, TimestampingError, check_timestamp, get_timestamp

from eln_common.errors import EntityNotFoundError, InvalidInputError
from eln_common.outbox import enqueue_event

from eln_common.errors import ServiceUnavailableError

from .models import (
    EntryAttachment,
    EntryRevision,
    EntryTimestamp,
    ExperimentApproval,
    AuditEvent,
    EquipmentBooking,
    EquipmentMaintenance,
    EquipmentResource,
    Experiment,
    InventoryItem,
    InventoryCustomFieldDefinition,
    LabTask,
    NotebookEntry,
    NotebookTemplate,
    RecordSignature,
    RecordTag,
    Sample,
    SampleCustodyTransfer,
    StockMovement,
    StorageLocation,
    WorkflowExecution,
    WorkflowRule,
)
from .attachment_storage import AttachmentStorage
from .repository import NotebookRepository


def _advance_maintenance_recurrence(
    value: datetime, interval: int, unit: str | None, anchor_day: int | None
) -> datetime:
    if unit == "weeks":
        return value + timedelta(weeks=interval)
    if unit == "months":
        month_index = value.year * 12 + value.month - 1 + interval
        year, month_zero_based = divmod(month_index, 12)
        month = month_zero_based + 1
        day = min(anchor_day or value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)
    return value + timedelta(days=interval)


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

    def _experiment_snapshot_digest(self, organization_id: int, experiment: Experiment) -> str:
        entries = list(self._db.scalars(
            select(NotebookEntry)
            .where(
                NotebookEntry.organization_id == organization_id,
                NotebookEntry.experiment_id == experiment.id,
            )
            .order_by(NotebookEntry.id)
        ))
        entry_ids = [entry.id for entry in entries]
        attachments = list(self._db.scalars(
            select(EntryAttachment)
            .where(
                EntryAttachment.organization_id == organization_id,
                EntryAttachment.entry_id.in_(entry_ids),
            )
            .order_by(EntryAttachment.entry_id, EntryAttachment.id)
        )) if entry_ids else []
        tag_scope = (RecordTag.entity_type == "experiment") & (
            RecordTag.entity_id == experiment.id
        )
        if entry_ids:
            tag_scope = tag_scope | (
                (RecordTag.entity_type == "entry")
                & RecordTag.entity_id.in_(entry_ids)
            )
        tags = list(self._db.scalars(
            select(RecordTag).where(
                RecordTag.organization_id == organization_id,
                tag_scope,
            ).order_by(RecordTag.entity_type, RecordTag.entity_id, RecordTag.tag)
        ))
        tag_map: dict[tuple[str, int], list[str]] = {}
        for tag in tags:
            tag_map.setdefault((tag.entity_type, tag.entity_id), []).append(tag.tag)
        attachments_by_entry: dict[int, list[dict[str, str | int]]] = {}
        for attachment in attachments:
            attachments_by_entry.setdefault(attachment.entry_id, []).append({
                "sha256": attachment.sha256,
                "filename": attachment.original_filename,
                "media_type": attachment.media_type,
                "size_bytes": attachment.size_bytes,
            })
        snapshot = {
            "experiment": {
                "id": experiment.id,
                "name": experiment.name,
                "description": experiment.description,
                "tags": tag_map.get(("experiment", experiment.id), []),
            },
            "entries": [
                {
                    "id": entry.id,
                    "title": entry.title,
                    "content": entry.content,
                    "tags": tag_map.get(("entry", entry.id), []),
                    "attachments": attachments_by_entry.get(entry.id, []),
                }
                for entry in entries
            ],
        }
        serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def list_experiment_approvals(
        self, organization_id: int, experiment_id: int
    ) -> list[ExperimentApproval]:
        self.get_experiment(organization_id, experiment_id)
        return list(self._db.scalars(
            select(ExperimentApproval)
            .where(
                ExperimentApproval.organization_id == organization_id,
                ExperimentApproval.experiment_id == experiment_id,
            )
            .order_by(ExperimentApproval.requested_at.desc(), ExperimentApproval.id.desc())
        ))

    def get_experiment_approval(
        self, organization_id: int, approval_id: int
    ) -> ExperimentApproval:
        approval = self._db.scalar(
            select(ExperimentApproval).where(
                ExperimentApproval.id == approval_id,
                ExperimentApproval.organization_id == organization_id,
            )
        )
        if approval is None:
            raise EntityNotFoundError("Experiment approval not found.")
        return approval

    def request_experiment_approval(
        self, organization_id: int, experiment_id: int, user_id: int,
        reviewer_user_ids: list[int], comment: str = "", review_mode: str = "sequential",
        rejection_reviewer_user_ids: list[int] | None = None,
    ) -> ExperimentApproval:
        rejection_reviewer_user_ids = rejection_reviewer_user_ids or []
        experiment = self.get_experiment(organization_id, experiment_id)
        if experiment.status != "in_progress":
            raise InvalidInputError("Only an in-progress experiment can be submitted for approval.")
        if not reviewer_user_ids or len(reviewer_user_ids) > 10:
            raise InvalidInputError("Choose between one and ten approval reviewers.")
        if review_mode not in {"sequential", "parallel"}:
            raise InvalidInputError("Approval review mode is invalid.")
        if rejection_reviewer_user_ids and review_mode != "sequential":
            raise InvalidInputError("A rejection review path requires sequential review mode.")
        if len(set(reviewer_user_ids + rejection_reviewer_user_ids)) != len(reviewer_user_ids + rejection_reviewer_user_ids):
            raise InvalidInputError("A reviewer can only appear once in the approval sequence.")
        if user_id in reviewer_user_ids + rejection_reviewer_user_ids:
            raise InvalidInputError("An experiment cannot be reviewed by its requester.")
        if len(rejection_reviewer_user_ids) > 10:
            raise InvalidInputError("Choose up to ten rejection-path reviewers.")
        pending = self._db.scalar(
            select(ExperimentApproval.id).where(
                ExperimentApproval.organization_id == organization_id,
                ExperimentApproval.experiment_id == experiment_id,
                ExperimentApproval.status == "pending",
            )
        )
        if pending is not None:
            raise InvalidInputError("This experiment already has a pending approval request.")
        approval = ExperimentApproval(
            organization_id=organization_id,
            experiment_id=experiment_id,
            requested_by_user_id=user_id,
            reviewer_user_id=reviewer_user_ids[0],
            reviewer_user_ids=list(reviewer_user_ids),
            rejection_reviewer_user_ids=list(rejection_reviewer_user_ids),
            review_mode=review_mode,
            active_branch="main",
            current_step_index=0,
            step_history=[
                {
                    "step_order": step_order,
                    "branch": "main",
                    "reviewer_user_id": reviewer_id,
                    "status": "pending",
                    "comment": "",
                    "decided_by_user_id": None,
                    "decided_at": None,
                }
                for step_order, reviewer_id in enumerate(reviewer_user_ids, start=1)
            ],
            status="pending",
            request_comment=comment.strip(),
            decision_comment="",
            snapshot_digest=self._experiment_snapshot_digest(organization_id, experiment),
        )
        self._db.add(approval)
        try:
            self._db.flush()
        except IntegrityError as error:
            self._db.rollback()
            raise InvalidInputError(
                "This experiment already has a pending approval request."
            ) from error
        enqueue_event(
            self._db,
            source_service="notebook",
            action="experiment_approval_requested",
            entity_type="experiment_approval",
            entity_id=approval.id,
            organization_id=organization_id,
            details={
                "experiment_id": str(experiment_id),
                "project_id": str(experiment.project_id),
                "experiment_name": experiment.name,
                "reviewer_user_ids": ",".join(str(reviewer_id) for reviewer_id in reviewer_user_ids),
                "rejection_reviewer_user_ids": ",".join(str(reviewer_id) for reviewer_id in rejection_reviewer_user_ids),
                "review_mode": review_mode,
                "requested_by_user_id": str(user_id),
                "snapshot_digest": approval.snapshot_digest,
            },
        )
        self._db.commit()
        self._db.refresh(approval)
        return approval

    def decide_experiment_approval(
        self, organization_id: int, approval_id: int, user_id: int,
        is_admin: bool, status: str, comment: str = "",
    ) -> ExperimentApproval:
        approval = self._db.scalar(
            select(ExperimentApproval)
            .where(
                ExperimentApproval.id == approval_id,
                ExperimentApproval.organization_id == organization_id,
            )
            .with_for_update()
        )
        if approval is None:
            raise EntityNotFoundError("Experiment approval not found.")
        if approval.status != "pending":
            raise InvalidInputError("Only a pending approval can receive a decision.")
        if user_id == approval.requested_by_user_id:
            raise InvalidInputError("The approval requester cannot decide their own request.")
        if status not in {"approved", "rejected"}:
            raise InvalidInputError("Approval decision must be approved or rejected.")
        experiment = self.get_experiment(organization_id, approval.experiment_id)
        now = datetime.now(timezone.utc)
        history = [dict(step, branch=step.get("branch", "main")) for step in approval.step_history]
        active_branch = approval.active_branch or "main"
        active_indexes = [index for index, step in enumerate(history) if step.get("branch") == active_branch]
        pending_indexes = [index for index in active_indexes if history[index].get("status") == "pending"]
        if approval.review_mode == "sequential":
            if approval.current_step_index < 0 or approval.current_step_index >= len(active_indexes):
                raise InvalidInputError("Approval sequence is invalid; submit a new request.")
            step_index = active_indexes[approval.current_step_index]
            if history[step_index].get("status") != "pending":
                raise InvalidInputError("The current approval step is no longer pending.")
            if not is_admin and approval.reviewer_user_id != user_id:
                raise InvalidInputError("Only the assigned reviewer or an organization admin can decide this approval.")
        else:
            if not pending_indexes:
                raise InvalidInputError("No pending reviewers remain in this approval.")
            if not is_admin and user_id not in approval.reviewer_user_ids:
                raise InvalidInputError("Only an assigned reviewer or organization admin can decide this approval.")
            own_pending = [
                index for index in pending_indexes
                if history[index].get("reviewer_user_id") == user_id
            ]
            if not is_admin and not own_pending:
                raise InvalidInputError("This reviewer has already decided this approval.")
            step_index = own_pending[0] if own_pending else pending_indexes[0]
        if status == "approved" and self._experiment_snapshot_digest(organization_id, experiment) != approval.snapshot_digest:
            stale_indexes = pending_indexes if approval.review_mode == "parallel" else active_indexes[approval.current_step_index:]
            for index in stale_indexes:
                step = dict(history[index])
                if step.get("status") != "pending":
                    continue
                step["status"] = "stale"
                if index == step_index:
                    step["comment"] = "The experiment changed after this review was requested. Submit a new approval request."
                    step["decided_by_user_id"] = user_id
                    step["decided_at"] = now.isoformat()
                history[index] = step
            approval.step_history = history
            approval.status = "stale"
            for index, stale_step in enumerate(history):
                if stale_step.get("status") == "pending":
                    stale_step["status"] = "stale"
                    history[index] = stale_step
            approval.step_history = history
            approval.decision_comment = "The experiment changed after this review was requested. Submit a new approval request."
            approval.decided_by_user_id = user_id
            approval.decided_at = now
            action = "experiment_approval_stale"
        else:
            step = dict(history[step_index])
            step["status"] = status
            step["comment"] = comment.strip()
            step["decided_by_user_id"] = user_id
            step["decided_at"] = now.isoformat()
            history[step_index] = step
            approval.step_history = history
            approval.decision_comment = comment.strip()
            if status == "rejected":
                if active_branch == "main" and approval.rejection_reviewer_user_ids:
                    for index in active_indexes:
                        if history[index].get("status") == "pending":
                            cancelled_step = dict(history[index])
                            cancelled_step["status"] = "not_required"
                            cancelled_step["comment"] = "The main approval path ended after a reviewer rejected it."
                            history[index] = cancelled_step
                    approval.active_branch = "rejection"
                    approval.current_step_index = 0
                    approval.reviewer_user_id = approval.rejection_reviewer_user_ids[0]
                    start_order = max((int(item.get("step_order", 0)) for item in history), default=0) + 1
                    history.extend({
                        "step_order": start_order + offset,
                        "branch": "rejection",
                        "reviewer_user_id": reviewer_id,
                        "status": "pending",
                        "comment": "",
                        "decided_by_user_id": None,
                        "decided_at": None,
                    } for offset, reviewer_id in enumerate(approval.rejection_reviewer_user_ids))
                    approval.step_history = history
                    action = "experiment_approval_branch_started"
                else:
                    for index, pending_step in enumerate(history):
                        if index != step_index and pending_step.get("status") == "pending":
                            cancelled_step = dict(pending_step)
                            cancelled_step["status"] = "not_required"
                            cancelled_step["comment"] = "The approval sequence ended after a reviewer rejected it."
                            history[index] = cancelled_step
                    approval.step_history = history
                    approval.status = "rejected"
                    approval.decided_by_user_id = user_id
                    approval.decided_at = now
                    action = "experiment_approval_rejected"
            elif approval.review_mode == "parallel":
                pending_indexes = [
                    index for index, history_step in enumerate(history)
                    if history_step.get("status") == "pending"
                ]
                if pending_indexes:
                    approval.current_step_index = pending_indexes[0]
                    approval.reviewer_user_id = int(history[pending_indexes[0]]["reviewer_user_id"])
                    action = "experiment_approval_step_approved"
                else:
                    approval.status = "approved"
                    approval.decided_by_user_id = user_id
                    approval.decided_at = now
                    action = "experiment_approval_approved"
            elif approval.current_step_index + 1 < len(active_indexes):
                approval.current_step_index += 1
                next_index = active_indexes[approval.current_step_index]
                approval.reviewer_user_id = int(history[next_index]["reviewer_user_id"])
                action = "experiment_approval_step_approved"
            else:
                approval.status = "approved"
                approval.decided_by_user_id = user_id
                approval.decided_at = now
                action = "experiment_approval_approved"
        if approval.status in {"approved", "rejected", "stale"}:
            self._run_workflow_rules(
                organization_id,
                experiment.project_id,
                user_id,
                experiment,
                "experiment_approval_ended",
                str(uuid.uuid4()),
                approval_outcome=approval.status,
            )
        enqueue_event(
            self._db,
            source_service="notebook",
            action=action,
            entity_type="experiment_approval",
            entity_id=approval.id,
            organization_id=organization_id,
            details={
                "experiment_id": str(approval.experiment_id),
                "project_id": str(experiment.project_id),
                "experiment_name": experiment.name,
                "requested_by_user_id": str(approval.requested_by_user_id),
                "approval_id": str(approval.id),
                "decided_by_user_id": str(user_id),
                "status": approval.status,
                "step_order": str(history[step_index].get("step_order", step_index + 1)),
                "step_count": str(len(history)),
                "review_mode": approval.review_mode,
                "active_branch": approval.active_branch,
                "reviewer_user_ids": ",".join(str(reviewer_id) for reviewer_id in (approval.rejection_reviewer_user_ids if approval.active_branch == "rejection" else approval.reviewer_user_ids)),
                "next_reviewer_user_id": str(approval.reviewer_user_id) if approval.status == "pending" and approval.review_mode == "sequential" else "",
            },
        )
        self._db.commit()
        self._db.refresh(approval)
        return approval

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
        if status == "completed":
            latest_approval = self._db.scalar(
                select(ExperimentApproval)
                .where(
                    ExperimentApproval.organization_id == organization_id,
                    ExperimentApproval.experiment_id == experiment_id,
                )
                .order_by(ExperimentApproval.requested_at.desc(), ExperimentApproval.id.desc())
                .limit(1)
            )
            if latest_approval is not None:
                current_digest = self._experiment_snapshot_digest(organization_id, experiment)
                if latest_approval.status == "approved" and latest_approval.snapshot_digest != current_digest:
                    latest_approval.status = "stale"
                    latest_approval.decision_comment = "The experiment changed after approval. Submit a new approval request."
                    self._run_workflow_rules(
                        organization_id,
                        experiment.project_id,
                        user_id,
                        experiment,
                        "experiment_approval_ended",
                        str(uuid.uuid4()),
                        approval_outcome="stale",
                    )
                    enqueue_event(
                        self._db,
                        source_service="notebook",
                        action="experiment_approval_stale",
                        entity_type="experiment_approval",
                        entity_id=latest_approval.id,
                        organization_id=organization_id,
                        details={
                            "experiment_id": str(experiment_id),
                            "project_id": str(experiment.project_id),
                            "experiment_name": experiment.name,
                            "requested_by_user_id": str(latest_approval.requested_by_user_id),
                            "approval_id": str(latest_approval.id),
                            "review_mode": latest_approval.review_mode,
                            "status": "stale",
                        },
                    )
                    self._db.commit()
                    raise InvalidInputError(
                        "The experiment changed after review; request approval again before completing it."
                    )
                if latest_approval.status != "approved":
                    raise InvalidInputError(
                        "A current approved review is required before completing this experiment."
                    )
        if experiment.status == status:
            return experiment
        previous_status = experiment.status
        transition_id = str(uuid.uuid4())
        experiment.status = status
        self._run_workflow_rules(
            organization_id,
            experiment.project_id,
            user_id,
            experiment,
            "experiment_status_changed",
            transition_id,
            from_status=previous_status,
            to_status=status,
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
        self, organization_id: int, project_id: int, name: str, description: str,
        user_id: int | None = None,
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
        self._run_workflow_rules(
            organization_id, project_id, user_id, experiment,
            "experiment_created", str(uuid.uuid4()),
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

    def _run_workflow_rules(
        self,
        organization_id: int,
        project_id: int,
        user_id: int | None,
        experiment: Experiment,
        trigger_type: str,
        event_id: str,
        *,
        from_status: str | None = None,
        to_status: str | None = None,
        approval_outcome: str | None = None,
    ) -> None:
        conditions = [
            WorkflowRule.organization_id == organization_id,
            WorkflowRule.project_id == project_id,
            WorkflowRule.enabled.is_(True),
            WorkflowRule.trigger_type == trigger_type,
        ]
        if trigger_type == "experiment_status_changed":
            conditions.extend([
                WorkflowRule.to_status == to_status,
                (WorkflowRule.from_status == from_status) | WorkflowRule.from_status.is_(None),
            ])
        elif trigger_type == "experiment_approval_ended":
            conditions.append(
                (WorkflowRule.approval_outcome == approval_outcome)
                | WorkflowRule.approval_outcome.is_(None)
            )
        rules = list(self._db.scalars(select(WorkflowRule).where(*conditions)))
        for rule in rules:
            now = datetime.now(timezone.utc)
            task = LabTask(
                organization_id=organization_id,
                project_id=project_id,
                experiment_id=experiment.id,
                assigned_to_user_id=rule.assigned_to_user_id,
                created_by_user_id=user_id or rule.created_by_user_id,
                title=rule.task_title,
                description=rule.task_description,
                priority=rule.task_priority,
                due_at=now + timedelta(days=rule.due_days) if rule.due_days is not None else None,
            )
            self._db.add(task)
            self._db.flush()
            self._db.add(WorkflowExecution(
                organization_id=organization_id,
                rule_id=rule.id,
                transition_id=event_id,
                experiment_id=experiment.id,
                task_id=task.id,
            ))
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
                    "trigger_type": trigger_type,
                    "event_id": event_id,
                    "approval_outcome": approval_outcome or "",
                },
            )

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
        normalized_name = values["name"].strip()
        task_title = values["task_title"].strip()
        if not normalized_name or not task_title:
            raise InvalidInputError("Workflow rule name and task title cannot be blank.")
        values = {**values, "name": normalized_name, "task_title": task_title}
        self._validate_workflow_trigger(values)
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

    def update_workflow_rule(
        self,
        organization_id: int,
        project_id: int,
        rule_id: int,
        user_id: int,
        values: dict,
    ) -> WorkflowRule:
        rule = self._db.scalar(
            select(WorkflowRule).where(
                WorkflowRule.organization_id == organization_id,
                WorkflowRule.project_id == project_id,
                WorkflowRule.id == rule_id,
            )
        )
        if rule is None:
            raise EntityNotFoundError("Workflow rule not found.")
        if not values:
            raise InvalidInputError("Provide at least one workflow rule field to update.")
        updates = dict(values)
        for field in ("name", "task_title", "task_description", "task_priority", "trigger_type"):
            if field in updates:
                if updates[field] is None:
                    raise InvalidInputError(f"Workflow rule {field} cannot be null.")
                if field in {"name", "task_title"}:
                    updates[field] = updates[field].strip()
                    if not updates[field]:
                        raise InvalidInputError(f"Workflow rule {field} cannot be blank.")
        candidate = {
            "trigger_type": updates.get("trigger_type", rule.trigger_type),
            "from_status": updates.get("from_status", rule.from_status),
            "to_status": updates.get("to_status", rule.to_status),
            "approval_outcome": updates.get("approval_outcome", rule.approval_outcome),
        }
        self._validate_workflow_trigger(candidate)
        for field, value in updates.items():
            setattr(rule, field, value)
        enqueue_event(
            self._db,
            source_service="notebook",
            action="workflow_rule_updated",
            entity_type="workflow_rule",
            entity_id=rule.id,
            organization_id=organization_id,
            details={"project_id": str(project_id), "changed_by_user_id": str(user_id)},
        )
        self._db.commit()
        self._db.refresh(rule)
        return rule

    @staticmethod
    def _validate_workflow_trigger(values: dict) -> None:
        trigger_type = values.get("trigger_type", "experiment_status_changed")
        from_status = values.get("from_status")
        to_status = values.get("to_status")
        approval_outcome = values.get("approval_outcome")
        if trigger_type == "experiment_status_changed":
            if approval_outcome is not None:
                raise InvalidInputError("Approval outcomes only apply to approval-ended triggers.")
            if to_status is None:
                raise InvalidInputError("Choose a destination status for this workflow trigger.")
            if from_status == to_status:
                raise InvalidInputError("Workflow transition statuses must differ.")
        elif trigger_type == "experiment_approval_ended":
            if from_status is not None or to_status is not None:
                raise InvalidInputError("Status conditions only apply to experiment status triggers.")
        elif from_status is not None or to_status is not None or approval_outcome is not None:
            raise InvalidInputError("Conditions do not apply to this workflow trigger.")

    def set_workflow_rule_enabled(
        self,
        organization_id: int,
        project_id: int,
        rule_id: int,
        user_id: int,
        enabled: bool,
    ) -> WorkflowRule:
        rule = self._db.scalar(
            select(WorkflowRule).where(
                WorkflowRule.organization_id == organization_id,
                WorkflowRule.project_id == project_id,
                WorkflowRule.id == rule_id,
            )
        )
        if rule is None:
            raise EntityNotFoundError("Workflow rule not found.")
        if rule.enabled != enabled:
            rule.enabled = enabled
            enqueue_event(
                self._db,
                source_service="notebook",
                action="workflow_rule_enabled" if enabled else "workflow_rule_disabled",
                entity_type="workflow_rule",
                entity_id=rule.id,
                organization_id=organization_id,
                details={"project_id": str(project_id), "changed_by_user_id": str(user_id)},
            )
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

    def update_storage_location(
        self, organization_id: int, user_id: int, location_id: int, values: dict
    ) -> StorageLocation:
        location = self._db.scalar(
            select(StorageLocation).where(
                StorageLocation.id == location_id,
                StorageLocation.organization_id == organization_id,
                StorageLocation.status == "active",
            )
        )
        if location is None:
            raise EntityNotFoundError("Storage location not found.")
        if not values:
            raise InvalidInputError("Provide at least one location field to update.")
        updates = dict(values)
        if any(
            field in updates and updates[field] is None
            for field in ("code", "name", "location_type", "description")
        ):
            raise InvalidInputError("Location fields cannot be null.")
        for field in ("code", "name"):
            if field in updates:
                updates[field] = updates[field].strip()
                if not updates[field]:
                    raise InvalidInputError(f"Location {field} cannot be blank.")
        if "code" in updates and self._db.scalar(
            select(StorageLocation.id).where(
                StorageLocation.organization_id == organization_id,
                StorageLocation.code == updates["code"],
                StorageLocation.id != location_id,
            )
        ) is not None:
            raise InvalidInputError("A location with this code already exists.")
        if "parent_id" in updates and updates["parent_id"] is not None:
            parent_id = updates["parent_id"]
            parent = self._db.scalar(
                select(StorageLocation).where(
                    StorageLocation.id == parent_id,
                    StorageLocation.organization_id == organization_id,
                    StorageLocation.status == "active",
                )
            )
            if parent is None:
                raise EntityNotFoundError("Parent storage location not found.")
            ancestor_id: int | None = parent_id
            while ancestor_id is not None:
                if ancestor_id == location_id:
                    raise InvalidInputError("A location cannot be nested beneath itself.")
                ancestor_id = self._db.scalar(
                    select(StorageLocation.parent_id).where(
                        StorageLocation.id == ancestor_id,
                        StorageLocation.organization_id == organization_id,
                    )
                )
        for field, value in updates.items():
            setattr(location, field, value)
        enqueue_event(
            self._db,
            source_service="notebook",
            action="updated",
            entity_type="storage_location",
            entity_id=location.id,
            organization_id=organization_id,
            details={"changed_by_user_id": str(user_id)},
        )
        self._db.commit()
        self._db.refresh(location)
        return location

    def set_storage_location_status(
        self, organization_id: int, user_id: int, location_id: int, status: str
    ) -> StorageLocation:
        if status not in {"active", "archived"}:
            raise InvalidInputError("Storage location status is invalid.")
        location = self._db.scalar(
            select(StorageLocation).where(
                StorageLocation.id == location_id,
                StorageLocation.organization_id == organization_id,
            )
        )
        if location is None:
            raise EntityNotFoundError("Storage location not found.")
        if location.status == status:
            return location
        if status == "archived":
            if self._db.scalar(
                select(StorageLocation.id).where(
                    StorageLocation.organization_id == organization_id,
                    StorageLocation.parent_id == location_id,
                    StorageLocation.status == "active",
                ).limit(1)
            ) is not None:
                raise InvalidInputError(
                    "Archive active child locations before archiving their parent."
                )
            active_assignment = any(
                self._db.scalar(
                    select(model.id).where(
                        model.organization_id == organization_id,
                        getattr(model, location_field) == location_id,
                        model.status == "active",
                    ).limit(1)
                ) is not None
                for model, location_field in (
                    (InventoryItem, "location_id"),
                    (Sample, "storage_location_id"),
                    (EquipmentResource, "storage_location_id"),
                )
            )
            if active_assignment:
                raise InvalidInputError(
                    "Move active inventory, samples, and equipment before archiving this location."
                )
        elif location.parent_id is not None:
            parent = self._db.scalar(
                select(StorageLocation).where(
                    StorageLocation.id == location.parent_id,
                    StorageLocation.organization_id == organization_id,
                    StorageLocation.status == "active",
                )
            )
            if parent is None:
                raise InvalidInputError("Restore this location's parent first.")
        location.status = status
        enqueue_event(
            self._db,
            source_service="notebook",
            action=f"storage_location_{status}",
            entity_type="storage_location",
            entity_id=location.id,
            organization_id=organization_id,
            details={"changed_by_user_id": str(user_id)},
        )
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

    def verify_entry_timestamp(
        self, organization_id: int, entry_id: int, timestamp_id: int
    ) -> dict:
        record = self.get_entry_timestamp(organization_id, entry_id, timestamp_id)
        certificate_path = os.getenv("ELN_TSA_CERTIFICATE_FILE", "").strip()
        if not certificate_path:
            raise ServiceUnavailableError(
                "TSA verification is not configured. Set ELN_TSA_CERTIFICATE_FILE "
                "to the pinned signer certificate."
            )
        try:
            certificate = Path(certificate_path).read_bytes()
        except OSError as error:
            raise ServiceUnavailableError(
                "The configured TSA signer certificate could not be read."
            ) from error

        snapshot = record.snapshot_json.encode("utf-8")
        snapshot_hash = hashlib.sha256(snapshot).hexdigest()
        digest_matches = hmac.compare_digest(snapshot_hash, record.record_sha256)
        token_valid = False
        token_time = None
        try:
            token_valid = bool(
                check_timestamp(
                    record.token_der,
                    certificate=certificate,
                    data=snapshot,
                    hashname="sha256",
                )
            )
            token_time = get_timestamp(record.token_der)
            if token_time.tzinfo is None:
                token_time = token_time.replace(tzinfo=timezone.utc)
            else:
                token_time = token_time.astimezone(timezone.utc)
        except Exception:
            # Verification failures are reported as a negative result, not as a
            # server error containing cryptographic parser details.
            token_valid = False

        stored_time = record.tsa_time
        if stored_time.tzinfo is None:
            stored_time = stored_time.replace(tzinfo=timezone.utc)
        else:
            stored_time = stored_time.astimezone(timezone.utc)
        stored_time_matches = (
            token_time is not None
            and abs((token_time - stored_time).total_seconds()) <= 1
        )
        valid = digest_matches and token_valid and stored_time_matches
        if valid:
            message = "The snapshot digest and RFC 3161 token verify against the configured pinned TSA signer certificate."
        elif not digest_matches:
            message = "The stored snapshot does not match its recorded SHA-256 digest."
        elif not token_valid:
            message = "The RFC 3161 token signature or message imprint did not verify."
        else:
            message = "The token time does not match the timestamp stored with this record."
        return {
            "timestamp_id": record.id,
            "snapshot_sha256": snapshot_hash,
            "recorded_sha256": record.record_sha256,
            "digest_matches": digest_matches,
            "token_valid_for_snapshot": token_valid,
            "token_time": token_time,
            "stored_time_matches": stored_time_matches,
            "valid": valid,
            "message": message,
        }

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
                    "experiment_id": str(task.experiment_id or ""),
                },
            )
            if status == "completed" and task.experiment_id:
                experiment = self._repository.get_experiment(organization_id, task.experiment_id)
                if experiment and experiment.status == "in_progress":
                    exp_tasks = [
                        t
                        for t in self._repository.list_tasks(organization_id, task.project_id)
                        if t.experiment_id == task.experiment_id
                    ]
                    if exp_tasks and all(t.status in {"completed", "cancelled"} for t in exp_tasks):
                        enqueue_event(
                            self._db,
                            source_service="notebook",
                            action="experiment_all_tasks_completed",
                            entity_type="experiment",
                            entity_id=experiment.id,
                            organization_id=organization_id,
                            details={
                                "project_id": str(task.project_id),
                                "experiment_id": str(experiment.id),
                                "experiment_name": experiment.name,
                                "created_by_user_id": str(getattr(experiment, "created_by_user_id", user_id)),
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
        record = (
            self._repository.get_sample(organization_id, entity_id, lock=True)
            if entity_type == "sample"
            else self._db.get(model, entity_id)
        )
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
        if (
            entity_type == "equipment"
            and status == "archived"
            and self._repository.has_active_equipment_maintenance(organization_id, entity_id)
        ):
            raise InvalidInputError(
                "Equipment with scheduled or in-progress maintenance cannot be archived."
            )
        if (
            entity_type == "sample"
            and status == "archived"
            and self._repository.has_active_sample_children(organization_id, entity_id)
        ):
            raise InvalidInputError(
                "Samples with active derived samples cannot be archived."
            )
        if record.status != status:
            if entity_type == "sample" and status == "archived":
                pending_transfer = self._repository.get_pending_sample_custody_transfer(
                    organization_id, entity_id
                )
                if pending_transfer is not None:
                    pending_transfer.status = "cancelled"
                    enqueue_event(
                        self._db,
                        source_service="notebook",
                        action="custody_transfer_cancelled",
                        entity_type="sample",
                        entity_id=entity_id,
                        organization_id=organization_id,
                        details={
                            "sample_name": record.name,
                            "transfer_id": str(pending_transfer.id),
                            "to_user_id": str(pending_transfer.to_user_id),
                            "reason": "sample_archived",
                        },
                    )
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

    def list_audit_events(
        self, organization_id: int, entity_type: str | None = None, entity_id: int | None = None
    ) -> list[AuditEvent]:
        return self._repository.list_audit_events(
            organization_id, entity_type=entity_type, entity_id=entity_id
        )

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
        self, organization_id: int, experiment_id: int, title: str, content: str,
        user_id: int | None = None,
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
        self._run_workflow_rules(
            organization_id, experiment.project_id, user_id, experiment,
            "entry_created", str(uuid.uuid4()),
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

    def list_inventory_custom_fields(
        self, organization_id: int, active_only: bool = True
    ) -> list[InventoryCustomFieldDefinition]:
        query = select(InventoryCustomFieldDefinition).where(
            InventoryCustomFieldDefinition.organization_id == organization_id
        )
        if active_only:
            query = query.where(InventoryCustomFieldDefinition.status == "active")
        return list(self._db.scalars(query.order_by(InventoryCustomFieldDefinition.name)))

    def create_inventory_custom_field(
        self, organization_id: int, user_id: int, values: dict
    ) -> InventoryCustomFieldDefinition:
        name = values["name"].strip()
        if not name:
            raise InvalidInputError("Custom field name cannot be blank.")
        existing = self._db.scalars(
            select(InventoryCustomFieldDefinition).where(
                InventoryCustomFieldDefinition.organization_id == organization_id
            )
        )
        if any(field.name.casefold() == name.casefold() for field in existing):
            raise InvalidInputError("A custom field with this name already exists.")
        field = InventoryCustomFieldDefinition(
            organization_id=organization_id,
            created_by_user_id=user_id,
            **{**values, "name": name},
        )
        self._db.add(field)
        self._db.flush()
        enqueue_event(
            self._db,
            source_service="notebook",
            action="inventory_custom_field_created",
            entity_type="inventory_custom_field",
            entity_id=field.id,
            organization_id=organization_id,
            details={
                "name": field.name,
                "field_type": field.field_type,
                "required": str(field.required).lower(),
                "changed_by_user_id": str(user_id),
            },
        )
        self._db.commit()
        self._db.refresh(field)
        return field

    def set_inventory_custom_field_status(
        self, organization_id: int, field_id: int, status: str
    ) -> InventoryCustomFieldDefinition:
        field = self._db.scalar(
            select(InventoryCustomFieldDefinition).where(
                InventoryCustomFieldDefinition.id == field_id,
                InventoryCustomFieldDefinition.organization_id == organization_id,
            )
        )
        if field is None:
            raise EntityNotFoundError("Inventory custom field not found.")
        if field.status != status:
            field.status = status
            enqueue_event(
                self._db,
                source_service="notebook",
                action="inventory_custom_field_archived" if status == "archived" else "inventory_custom_field_restored",
                entity_type="inventory_custom_field",
                entity_id=field.id,
                organization_id=organization_id,
                details={"name": field.name},
            )
            self._db.commit()
            self._db.refresh(field)
        return field

    def update_inventory_custom_field(
        self, organization_id: int, user_id: int, field_id: int, values: dict
    ) -> InventoryCustomFieldDefinition:
        field = self._db.scalar(
            select(InventoryCustomFieldDefinition).where(
                InventoryCustomFieldDefinition.id == field_id,
                InventoryCustomFieldDefinition.organization_id == organization_id,
            )
        )
        if field is None:
            raise EntityNotFoundError("Inventory custom field not found.")

        name = values["name"].strip()
        if not name:
            raise InvalidInputError("Custom field name cannot be blank.")
        collisions = self._db.scalars(
            select(InventoryCustomFieldDefinition).where(
                InventoryCustomFieldDefinition.organization_id == organization_id,
                InventoryCustomFieldDefinition.id != field_id,
            )
        )
        if any(other.name.casefold() == name.casefold() for other in collisions):
            raise InvalidInputError("A custom field with this name already exists.")

        old_name = field.name
        old_type = field.field_type
        old_name_key = old_name.casefold()
        new_name_key = name.casefold()
        inventory_items = self._db.scalars(
            select(InventoryItem).where(
                InventoryItem.organization_id == organization_id
            )
        )
        updated_values: list[tuple[InventoryItem, dict[str, str]]] = []
        for item in inventory_items:
            custom_fields = dict(item.custom_fields or {})
            matching_keys = [key for key in custom_fields if key.casefold() == old_name_key]
            if len(matching_keys) > 1:
                raise InvalidInputError(
                    f"Inventory item {item.id} has ambiguous values for {old_name}."
                )
            old_key = matching_keys[0] if matching_keys else None
            existing_new_key = next(
                (key for key in custom_fields if key.casefold() == new_name_key),
                None,
            )
            value = (
                custom_fields.get(old_key, "")
                if old_key
                else custom_fields.get(existing_new_key, "") if existing_new_key else ""
            )
            self._validate_inventory_custom_field_value(
                name,
                values["field_type"],
                False,
                values["options"],
                value,
            )
            if old_key is not None and old_name_key != new_name_key:
                if existing_new_key is not None and existing_new_key != old_key and custom_fields[existing_new_key] != value:
                    raise InvalidInputError(
                        f"Inventory item {item.id} already has a different value for {name}."
                    )
                if existing_new_key is not None and existing_new_key != old_key:
                    custom_fields.pop(existing_new_key)
                custom_fields.pop(old_key)
                custom_fields[name] = value
                updated_values.append((item, custom_fields))
            elif old_key is not None and old_key != name:
                custom_fields.pop(old_key)
                custom_fields[name] = value
                updated_values.append((item, custom_fields))
            elif old_key is None and existing_new_key is not None and existing_new_key != name:
                custom_fields.pop(existing_new_key)
                custom_fields[name] = value
                updated_values.append((item, custom_fields))

        for item, custom_fields in updated_values:
            item.custom_fields = custom_fields
        field.name = name
        field.field_type = values["field_type"]
        field.required = values["required"]
        field.options = values["options"]
        enqueue_event(
            self._db,
            source_service="notebook",
            action="inventory_custom_field_updated",
            entity_type="inventory_custom_field",
            entity_id=field.id,
            organization_id=organization_id,
            details={
                "previous_name": old_name,
                "name": name,
                "previous_field_type": old_type,
                "field_type": field.field_type,
                "changed_by_user_id": str(user_id),
                "updated_inventory_value_count": str(len(updated_values)),
            },
        )
        self._db.commit()
        self._db.refresh(field)
        return field

    @staticmethod
    def _validate_inventory_custom_field_value(
        name: str, field_type: str, required: bool, options: list[str], raw_value: str
    ) -> None:
        value = str(raw_value or "").strip()
        if required and not value:
            raise InvalidInputError(f"{name} is required.")
        if not value:
            return
        if field_type == "number":
            try:
                number = Decimal(value)
                if not number.is_finite():
                    raise InvalidOperation
            except InvalidOperation as error:
                raise InvalidInputError(f"{name} must be a number.") from error
        elif field_type == "date":
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError as error:
                raise InvalidInputError(f"{name} must use YYYY-MM-DD format.") from error
        elif field_type == "boolean" and value.casefold() not in {"true", "false"}:
            raise InvalidInputError(f"{name} must be true or false.")
        elif field_type == "select" and value.casefold() not in {
            option.casefold() for option in options
        }:
            raise InvalidInputError(f"{name} must match a configured option.")

    def _validate_inventory_custom_fields(self, organization_id: int, values: dict) -> None:
        definitions = self.list_inventory_custom_fields(organization_id)
        values_by_name = {name.casefold(): value for name, value in values.items()}
        for definition in definitions:
            self._validate_inventory_custom_field_value(
                definition.name,
                definition.field_type,
                definition.required,
                definition.options,
                values_by_name.get(definition.name.casefold(), ""),
            )

    def create_inventory_item(
        self, organization_id: int, user_id: int, values: dict,
        validate_custom_fields: bool = True,
    ) -> InventoryItem:
        name = values["name"].strip()
        unit = values["unit"].strip()
        category = values["category"].strip()
        if not name or not unit or not category:
            raise InvalidInputError(
                "Inventory item name, category, and unit cannot be blank."
            )
        if validate_custom_fields:
            self._validate_inventory_custom_fields(
                organization_id, values.get("custom_fields", {})
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
        if parent_id is not None:
            parent = self._repository.get_sample(organization_id, parent_id, lock=True)
            if parent is None:
                raise EntityNotFoundError("Parent sample not found.")
            if parent.status != "active":
                raise InvalidInputError("Archived samples cannot be used as a parent.")
            if parent.project_id is not None:
                if values.get("project_id") not in {None, parent.project_id}:
                    raise InvalidInputError(
                        "A derived sample must remain in its parent sample's project."
                    )
                values["project_id"] = parent.project_id
        values["storage_location"] = self._location_label(
            organization_id,
            values.get("storage_location_id"),
            values.get("storage_location", ""),
        )
        sample = self._repository.add_sample(
            Sample(
                organization_id=organization_id,
                created_by_user_id=user_id,
                current_custodian_user_id=user_id,
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
            details={
                "name": sample.name,
                "sample_type": sample.sample_type,
                "parent_sample_id": str(parent_id) if parent_id is not None else "",
            },
        )
        self._db.commit()
        self._db.refresh(sample)
        return sample

    def list_sample_custody_transfers(
        self, organization_id: int, sample_id: int
    ) -> list[SampleCustodyTransfer]:
        if self._repository.get_sample(organization_id, sample_id) is None:
            raise EntityNotFoundError("Sample not found.")
        return self._repository.list_sample_custody_transfers(organization_id, sample_id)

    def list_pending_sample_custody_transfers_for_user(
        self, organization_id: int, user_id: int
    ) -> list[SampleCustodyTransfer]:
        return self._repository.list_pending_sample_custody_transfers_for_user(
            organization_id, user_id
        )

    def request_sample_custody_transfer(
        self, organization_id: int, sample_id: int, user_id: int,
        to_user_id: int, request_note: str = "",
    ) -> SampleCustodyTransfer:
        sample = self._repository.get_sample(organization_id, sample_id, lock=True)
        if sample is None:
            raise EntityNotFoundError("Sample not found.")
        if sample.status != "active":
            raise InvalidInputError("Archived samples cannot be transferred.")
        if sample.current_custodian_user_id != user_id:
            raise InvalidInputError("Only the current custodian can transfer this sample.")
        if to_user_id == user_id:
            raise InvalidInputError("A sample cannot be transferred to its current custodian.")
        if self._repository.get_pending_sample_custody_transfer(organization_id, sample_id):
            raise InvalidInputError("This sample already has a pending custody transfer.")
        try:
            transfer = self._repository.add_sample_custody_transfer(SampleCustodyTransfer(
                organization_id=organization_id,
                sample_id=sample_id,
                from_user_id=user_id,
                to_user_id=to_user_id,
                status="pending",
                request_note=request_note.strip(),
            ))
        except IntegrityError as error:
            self._db.rollback()
            raise InvalidInputError("This sample already has a pending custody transfer.") from error
        enqueue_event(
            self._db,
            source_service="notebook",
            action="custody_transfer_requested",
            entity_type="sample",
            entity_id=sample.id,
            organization_id=organization_id,
            details={
                "sample_name": sample.name,
                "transfer_id": str(transfer.id),
                "from_user_id": str(user_id),
                "to_user_id": str(to_user_id),
                "request_note": transfer.request_note,
            },
        )
        self._db.commit()
        self._db.refresh(transfer)
        return transfer

    def accept_sample_custody_transfer(
        self, organization_id: int, sample_id: int, transfer_id: int,
        user_id: int, receipt_note: str = "",
    ) -> SampleCustodyTransfer:
        sample = self._repository.get_sample(organization_id, sample_id, lock=True)
        if sample is None:
            raise EntityNotFoundError("Sample not found.")
        transfer = self._repository.get_sample_custody_transfer(
            organization_id, sample_id, transfer_id, lock=True
        )
        if transfer is None:
            raise EntityNotFoundError("Sample custody transfer not found.")
        if transfer.status != "pending":
            raise InvalidInputError("Only a pending sample transfer can be accepted.")
        if transfer.to_user_id != user_id:
            raise InvalidInputError("Only the designated recipient can accept this transfer.")
        if sample.status != "active" or sample.current_custodian_user_id != transfer.from_user_id:
            raise InvalidInputError("The sample custody changed; request a new transfer.")
        accepted_at = datetime.now(timezone.utc)
        sample.current_custodian_user_id = user_id
        transfer.status = "accepted"
        transfer.receipt_note = receipt_note.strip()
        transfer.accepted_at = accepted_at
        enqueue_event(
            self._db,
            source_service="notebook",
            action="custody_transfer_accepted",
            entity_type="sample",
            entity_id=sample.id,
            organization_id=organization_id,
            details={
                "sample_name": sample.name,
                "transfer_id": str(transfer.id),
                "from_user_id": str(transfer.from_user_id),
                "to_user_id": str(user_id),
                "receipt_note": transfer.receipt_note,
            },
        )
        self._db.commit()
        self._db.refresh(transfer)
        return transfer

    def cancel_sample_custody_transfer(
        self, organization_id: int, sample_id: int, transfer_id: int, user_id: int
    ) -> SampleCustodyTransfer:
        sample = self._repository.get_sample(organization_id, sample_id, lock=True)
        if sample is None:
            raise EntityNotFoundError("Sample not found.")
        transfer = self._repository.get_sample_custody_transfer(
            organization_id, sample_id, transfer_id, lock=True
        )
        if transfer is None:
            raise EntityNotFoundError("Sample custody transfer not found.")
        if transfer.status != "pending":
            raise InvalidInputError("Only a pending sample transfer can be cancelled.")
        if transfer.from_user_id != user_id:
            raise InvalidInputError("Only the current custodian can cancel this transfer.")
        transfer.status = "cancelled"
        enqueue_event(
            self._db,
            source_service="notebook",
            action="custody_transfer_cancelled",
            entity_type="sample",
            entity_id=sample.id,
            organization_id=organization_id,
            details={
                "sample_name": sample.name,
                "transfer_id": str(transfer.id),
                "from_user_id": str(user_id),
                "to_user_id": str(transfer.to_user_id),
                "reason": "sender_cancelled",
            },
        )
        self._db.commit()
        self._db.refresh(transfer)
        return transfer

    def move_sample(
        self, organization_id: int, sample_id: int, user_id: int, values: dict
    ) -> Sample:
        sample = self._repository.get_sample(organization_id, sample_id)
        if sample is None:
            raise EntityNotFoundError("Sample not found.")
        if sample.status != "active":
            raise InvalidInputError("Archived samples cannot be moved.")
        location_id = values.get("storage_location_id")
        location_note = values.get("storage_location", "").strip()
        location_label = self._location_label(organization_id, location_id, location_note)
        previous_id = sample.storage_location_id
        previous_label = sample.storage_location
        if previous_id == location_id and previous_label == location_label:
            return sample
        sample.storage_location_id = location_id
        sample.storage_location = location_label
        enqueue_event(
            self._db,
            source_service="notebook",
            action="location_changed",
            entity_type="sample",
            entity_id=sample.id,
            organization_id=organization_id,
            details={
                "changed_by_user_id": str(user_id),
                "from_location_id": str(previous_id or ""),
                "from_location": previous_label,
                "to_location_id": str(location_id or ""),
                "to_location": location_label,
            },
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
        user_id: int | None = None,
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
        self._run_workflow_rules(
            organization_id, project_id, user_id, experiment,
            "experiment_created", str(uuid.uuid4()),
        )
        self._run_workflow_rules(
            organization_id, project_id, user_id, experiment,
            "entry_created", str(uuid.uuid4()),
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
        if self._repository.has_maintenance_conflict(
            organization_id, equipment_id, starts_at, ends_at
        ):
            raise InvalidInputError("Equipment is unavailable during scheduled maintenance.")
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

    def create_bookings(
        self,
        organization_id: int,
        equipment_id: int,
        user_id: int,
        values_list: list[dict],
    ) -> list[EquipmentBooking]:
        try:
            equipment = self._repository.get_equipment(
                organization_id, equipment_id, lock=True
            )
            if equipment is None:
                raise EntityNotFoundError("Equipment not found.")
            if equipment.status != "active":
                raise InvalidInputError("Archived equipment cannot be booked.")
            if not values_list or len(values_list) > 100:
                raise InvalidInputError("A calendar import must contain between 1 and 100 bookings.")

            prepared: list[tuple[datetime, datetime, dict]] = []
            for values in values_list:
                starts_at = values["starts_at"]
                ends_at = values["ends_at"]
                if starts_at.tzinfo is None or ends_at.tzinfo is None or ends_at <= starts_at:
                    raise InvalidInputError("Booking end must be after its timezone-aware start.")
                starts_at = starts_at.astimezone(timezone.utc)
                ends_at = ends_at.astimezone(timezone.utc)
                if not values.get("purpose", "").strip():
                    raise InvalidInputError("Booking purpose cannot be blank.")
                if self._repository.has_booking_conflict(
                    organization_id, equipment_id, starts_at, ends_at
                ):
                    raise InvalidInputError("Equipment is already booked during an imported time window.")
                if self._repository.has_maintenance_conflict(
                    organization_id, equipment_id, starts_at, ends_at
                ):
                    raise InvalidInputError("Equipment maintenance overlaps an imported time window.")
                if any(starts_at < previous_end and ends_at > previous_start for previous_start, previous_end, _ in prepared):
                    raise InvalidInputError("Imported equipment bookings overlap each other.")
                prepared.append((starts_at, ends_at, values))

            created: list[EquipmentBooking] = []
            for starts_at, ends_at, values in prepared:
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
                created.append(booking)
            for booking in created:
                self._db.refresh(booking)
            self._db.commit()
            return created
        except Exception:
            self._db.rollback()
            raise

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

    def list_equipment_maintenance(self, organization_id: int) -> list[EquipmentMaintenance]:
        return self._repository.list_maintenance(organization_id)

    def update_equipment_maintenance(
        self, organization_id: int, maintenance_id: int, user_id: int, values: dict
    ) -> EquipmentMaintenance:
        maintenance = self._repository.get_maintenance(organization_id, maintenance_id)
        if maintenance is None:
            raise EntityNotFoundError("Equipment maintenance record not found.")
        if maintenance.status != "scheduled":
            raise InvalidInputError("Only scheduled maintenance can be edited.")
        if not values:
            raise InvalidInputError("Provide at least one maintenance field to update.")
        if any(value is None for field, value in values.items() if field not in {"recurrence_days", "recurrence_unit", "recurrence_until"}):
            raise InvalidInputError("Maintenance fields cannot be null.")
        for field in ("title", "notes", "service_provider", "service_contact_email", "service_contact_phone"):
            if field in values:
                values[field] = values[field].strip()
        if "title" in values and not values["title"]:
            raise InvalidInputError("Maintenance title cannot be blank.")

        starts_at = values.get("starts_at", maintenance.starts_at)
        ends_at = values.get("ends_at", maintenance.ends_at)
        if starts_at.tzinfo is None or ends_at.tzinfo is None or ends_at <= starts_at:
            raise InvalidInputError("Maintenance end must be after its timezone-aware start.")
        starts_at = starts_at.astimezone(timezone.utc)
        ends_at = ends_at.astimezone(timezone.utc)
        reset_month_anchor = "recurrence_unit" in values or "starts_at" in values
        recurrence_days = values.get("recurrence_days", maintenance.recurrence_days)
        recurrence_unit = values.get("recurrence_unit", maintenance.recurrence_unit) or ("days" if recurrence_days is not None else None)
        recurrence_until = values.get("recurrence_until", maintenance.recurrence_until)
        if recurrence_days is None:
            recurrence_unit = None
        elif recurrence_unit not in {"days", "weeks", "months"}:
            raise InvalidInputError("Choose days, weeks, or months for the recurrence interval.")
        if recurrence_until is not None:
            if recurrence_days is None:
                raise InvalidInputError("A recurrence end date requires a recurrence interval.")
            if recurrence_until < starts_at.date():
                raise InvalidInputError("Recurrence end date cannot precede this maintenance window.")
        if self._repository.has_booking_conflict(
            organization_id, maintenance.equipment_id, starts_at, ends_at
        ):
            raise InvalidInputError("Maintenance overlaps a reserved equipment booking.")
        if self._repository.has_maintenance_conflict(
            organization_id, maintenance.equipment_id, starts_at, ends_at,
            exclude_maintenance_id=maintenance.id,
        ):
            raise InvalidInputError("Maintenance overlaps another scheduled maintenance window.")
        values["starts_at"] = starts_at
        values["ends_at"] = ends_at
        values["recurrence_unit"] = recurrence_unit
        if recurrence_unit == "months":
            if reset_month_anchor:
                values["recurrence_anchor_day"] = starts_at.day
            elif maintenance.recurrence_anchor_day is None:
                values["recurrence_anchor_day"] = maintenance.starts_at.day
        else:
            values["recurrence_anchor_day"] = None
        for field, value in values.items():
            setattr(maintenance, field, value)
        enqueue_event(
            self._db, source_service="notebook", action="equipment_maintenance_updated",
            entity_type="equipment_maintenance", entity_id=maintenance.id,
            organization_id=organization_id,
            details={"equipment_id": str(maintenance.equipment_id), "updated_by_user_id": str(user_id)},
        )
        self._db.commit()
        self._db.refresh(maintenance)
        return maintenance

    def create_equipment_maintenance(
        self, organization_id: int, equipment_id: int, user_id: int, values: dict
    ) -> EquipmentMaintenance:
        equipment = self._repository.get_equipment(organization_id, equipment_id, lock=True)
        if equipment is None:
            raise EntityNotFoundError("Equipment not found.")
        if equipment.status != "active":
            raise InvalidInputError("Archived equipment cannot be scheduled for maintenance.")
        title = values["title"].strip()
        if not title:
            raise InvalidInputError("Maintenance title cannot be blank.")
        service_provider = values.get("service_provider", "").strip()
        starts_at = values["starts_at"].astimezone(timezone.utc)
        ends_at = values["ends_at"].astimezone(timezone.utc)
        recurrence_days = values.get("recurrence_days")
        recurrence_unit = (values.get("recurrence_unit") or "days") if recurrence_days is not None else None
        if self._repository.has_booking_conflict(organization_id, equipment_id, starts_at, ends_at):
            raise InvalidInputError("Maintenance overlaps a reserved equipment booking.")
        if self._repository.has_maintenance_conflict(organization_id, equipment_id, starts_at, ends_at):
            raise InvalidInputError("Maintenance overlaps another scheduled maintenance window.")
        maintenance = self._repository.add_maintenance(EquipmentMaintenance(
            organization_id=organization_id,
            equipment_id=equipment_id,
            created_by_user_id=user_id,
            title=title,
            notes=values.get("notes", "").strip(),
            service_provider=service_provider,
            service_contact_email=values.get("service_contact_email", "").strip(),
            service_contact_phone=values.get("service_contact_phone", "").strip(),
            recurrence_days=recurrence_days,
            recurrence_unit=recurrence_unit,
            recurrence_anchor_day=starts_at.day if recurrence_unit == "months" else None,
            recurrence_until=values.get("recurrence_until"),
            starts_at=starts_at,
            ends_at=ends_at,
            status="scheduled",
        ))
        enqueue_event(
            self._db, source_service="notebook", action="equipment_maintenance_scheduled",
            entity_type="equipment_maintenance", entity_id=maintenance.id,
            organization_id=organization_id,
            details={"equipment_id": str(equipment_id), "created_by_user_id": str(user_id),
                     "starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat()},
        )
        self._db.commit()
        self._db.refresh(maintenance)
        return maintenance

    def update_equipment_maintenance_status(
        self, organization_id: int, maintenance_id: int, user_id: int, status: str
    ) -> EquipmentMaintenance:
        maintenance = self._repository.get_maintenance(organization_id, maintenance_id)
        if maintenance is None:
            raise EntityNotFoundError("Equipment maintenance record not found.")
        allowed = {
            "scheduled": {"in_progress", "completed", "cancelled"},
            "in_progress": {"completed", "cancelled"},
        }
        if status not in allowed.get(maintenance.status, set()):
            raise InvalidInputError("That maintenance status transition is not allowed.")
        next_maintenance = None
        if status == "completed" and maintenance.recurrence_days is not None:
            duration = maintenance.ends_at - maintenance.starts_at
            # Preserve the existing end-plus-interval behavior for daily plans;
            # calendar-based weekly/monthly plans recur from the occurrence start.
            recurrence_base = maintenance.ends_at if maintenance.recurrence_unit in {None, "days"} else maintenance.starts_at
            next_start = _advance_maintenance_recurrence(
                recurrence_base,
                maintenance.recurrence_days,
                maintenance.recurrence_unit,
                maintenance.recurrence_anchor_day,
            )
            now = datetime.now(timezone.utc)
            while next_start <= now:
                next_start = _advance_maintenance_recurrence(
                    next_start,
                    maintenance.recurrence_days,
                    maintenance.recurrence_unit,
                    maintenance.recurrence_anchor_day,
                )
            next_end = next_start + duration
            if maintenance.recurrence_until is not None and next_start.date() > maintenance.recurrence_until:
                next_start = None
            if next_start is not None:
                if self._repository.has_booking_conflict(
                    organization_id, maintenance.equipment_id, next_start, next_end
                ) or self._repository.has_maintenance_conflict(
                    organization_id, maintenance.equipment_id, next_start, next_end
                ):
                    raise InvalidInputError(
                        "The next recurring maintenance window conflicts with a booking or maintenance window. Resolve the conflict before completing this occurrence."
                    )
                next_maintenance = EquipmentMaintenance(
                    organization_id=organization_id,
                    equipment_id=maintenance.equipment_id,
                    created_by_user_id=user_id,
                    title=maintenance.title,
                    notes=maintenance.notes,
                    service_provider=maintenance.service_provider,
                    service_contact_email=maintenance.service_contact_email,
                    service_contact_phone=maintenance.service_contact_phone,
                    recurrence_days=maintenance.recurrence_days,
                    recurrence_unit=maintenance.recurrence_unit,
                    recurrence_anchor_day=maintenance.recurrence_anchor_day,
                    recurrence_until=maintenance.recurrence_until,
                    starts_at=next_start,
                    ends_at=next_end,
                    status="scheduled",
                )
        previous_status = maintenance.status
        maintenance.status = status
        enqueue_event(
            self._db, source_service="notebook", action=f"equipment_maintenance_{status}",
            entity_type="equipment_maintenance", entity_id=maintenance.id,
            organization_id=organization_id,
            details={"equipment_id": str(maintenance.equipment_id),
                     "updated_by_user_id": str(user_id), "previous_status": previous_status,
                     "status": status},
        )
        if next_maintenance is not None:
            self._repository.add_maintenance(next_maintenance)
            enqueue_event(
                self._db,
                source_service="notebook",
                action="equipment_maintenance_scheduled",
                entity_type="equipment_maintenance",
                entity_id=next_maintenance.id,
                organization_id=organization_id,
                details={
                    "equipment_id": str(maintenance.equipment_id),
                    "created_by_user_id": str(user_id),
                    "recurring_from_id": str(maintenance.id),
                    "starts_at": next_maintenance.starts_at.isoformat(),
                    "ends_at": next_maintenance.ends_at.isoformat(),
                },
            )
        self._db.commit()
        self._db.refresh(maintenance)
        return maintenance
