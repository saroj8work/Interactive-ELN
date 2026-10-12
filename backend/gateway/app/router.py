import io
import json
import csv
from pathlib import PurePosixPath
from urllib.parse import quote
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import TypeAdapter, ValidationError

from eln_common.contracts import (
    AuditVerificationRead,
    AttachmentRead,
    ActivityEventRead,
    EntryCreate,
    EntryRead,
    EntryRevisionRead,
    EntryUpdate,
    EquipmentBookingCreate,
    EquipmentBookingRead,
    EquipmentCreate,
    EquipmentRead,
    ExperimentCreate,
    ExperimentRead,
    ExperimentStatusUpdate,
    InventoryItemCreate,
    InventoryItemRead,
    NotebookTemplateCreate,
    NotebookTemplateRead,
    NotebookTemplateUpdate,
    ProjectCreate,
    ProjectAccessRead,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectRead,
    ProjectImportPayload,
    ProjectImportResult,
    RecordTagSetRead,
    RecordTagSetUpdate,
    RecordSignatureCreate,
    RecordSignatureRead,
    SearchHit,
    SampleCreate,
    SampleRead,
    StockAdjustment,
    StockMovementRead,
    TaskCreate,
    TaskRead,
    TaskStatusUpdate,
    ResourceStatusUpdate,
)
from services.identity.app.security import Principal, get_principal

from .client import ServiceClient


def get_service_client(request: Request) -> ServiceClient:
    return request.app.state.service_client


ServiceClientDep = Annotated[ServiceClient, Depends(get_service_client)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
PROJECT_LIST = TypeAdapter(list[ProjectRead])
PROJECT = TypeAdapter(ProjectRead)
PROJECT_ACCESS = TypeAdapter(ProjectAccessRead)
PROJECT_MEMBERS = TypeAdapter(list[ProjectMemberRead])
PROJECT_MEMBER = TypeAdapter(ProjectMemberRead)
EXPERIMENT_LIST = TypeAdapter(list[ExperimentRead])
EXPERIMENT = TypeAdapter(ExperimentRead)
ENTRY_LIST = TypeAdapter(list[EntryRead])
ENTRY = TypeAdapter(EntryRead)
ENTRY_REVISIONS = TypeAdapter(list[EntryRevisionRead])
ATTACHMENTS = TypeAdapter(list[AttachmentRead])
ATTACHMENT = TypeAdapter(AttachmentRead)
INVENTORY_LIST = TypeAdapter(list[InventoryItemRead])
INVENTORY_ITEM = TypeAdapter(InventoryItemRead)
STOCK_MOVEMENTS = TypeAdapter(list[StockMovementRead])
STOCK_MOVEMENT = TypeAdapter(StockMovementRead)
EQUIPMENT_LIST = TypeAdapter(list[EquipmentRead])
EQUIPMENT = TypeAdapter(EquipmentRead)
BOOKINGS = TypeAdapter(list[EquipmentBookingRead])
BOOKING = TypeAdapter(EquipmentBookingRead)
TEMPLATE_LIST = TypeAdapter(list[NotebookTemplateRead])
TEMPLATE = TypeAdapter(NotebookTemplateRead)
SAMPLE_LIST = TypeAdapter(list[SampleRead])
SAMPLE = TypeAdapter(SampleRead)
SEARCH_HITS = TypeAdapter(list[SearchHit])
ACTIVITY_LIST = TypeAdapter(list[ActivityEventRead])
RECORD_TAG_SET = TypeAdapter(RecordTagSetRead)
RECORD_TAG_SETS = TypeAdapter(list[RecordTagSetRead])
TASK_LIST = TypeAdapter(list[TaskRead])
TASK = TypeAdapter(TaskRead)
PROJECT_IMPORT_RESULT = TypeAdapter(ProjectImportResult)
SIGNATURE_LIST = TypeAdapter(list[RecordSignatureRead])
SIGNATURE = TypeAdapter(RecordSignatureRead)
AUDIT_VERIFICATION = TypeAdapter(AuditVerificationRead)

projects_router = APIRouter(prefix="/api/projects", tags=["projects"])
notebook_router = APIRouter(tags=["notebook"])
activity_router = APIRouter(prefix="/api", tags=["activity"])
inventory_router = APIRouter(prefix="/api", tags=["inventory"])
templates_router = APIRouter(prefix="/api", tags=["templates"])
attachments_router = APIRouter(prefix="/api", tags=["attachments"])
search_router = APIRouter(prefix="/api", tags=["search"])
booking_router = APIRouter(prefix="/api", tags=["equipment"])


@projects_router.get("", response_model=list[ProjectRead])
async def list_projects(
    client: ServiceClientDep, principal: PrincipalDep
) -> list[ProjectRead]:
    return await client.get(
        "projects", "/projects", PROJECT_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@projects_router.post("", response_model=ProjectRead, status_code=201)
async def create_project(
    payload: ProjectCreate, client: ServiceClientDep, principal: PrincipalDep
) -> ProjectRead:
    return await client.post(
        "projects", "/projects", payload.model_dump(), PROJECT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@projects_router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int, client: ServiceClientDep, principal: PrincipalDep
) -> ProjectRead:
    return await client.get(
        "projects", f"/projects/{project_id}", PROJECT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@projects_router.get("/{project_id}/export")
async def export_project_records(
    project_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
    format: Literal["json", "csv", "zip"] = "json",
) -> Response:
    await _require_project_access(client, principal, project_id)
    project = await client.get(
        "projects",
        f"/projects/{project_id}",
        PROJECT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )
    experiments = await client.get(
        "notebook",
        f"/projects/{project_id}/experiments",
        EXPERIMENT_LIST,
        organization_id=principal.organization_id,
    )
    tasks = await client.get(
        "notebook",
        f"/projects/{project_id}/tasks",
        TASK_LIST,
        organization_id=principal.organization_id,
    )
    if len(experiments) > 1000:
        raise HTTPException(status_code=413, detail="Project contains too many experiments to export.")
    if len(tasks) > 5000:
        raise HTTPException(status_code=413, detail="Project contains too many tasks to export.")
    entries_by_experiment: list[list[EntryRead]] = []
    entry_count = 0
    for experiment in experiments:
        entries = await client.get(
            "notebook",
            f"/experiments/{experiment.id}/entries",
            ENTRY_LIST,
            organization_id=principal.organization_id,
        )
        entry_count += len(entries)
        if entry_count > 1000:
            raise HTTPException(status_code=413, detail="Project contains too many entries to export.")
        entries_by_experiment.append(entries)
    total_content_bytes = sum(
        len(entry.content.encode("utf-8"))
        for entries in entries_by_experiment
        for entry in entries
    ) + sum(len(task.description.encode("utf-8")) for task in tasks)
    if total_content_bytes > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Project notebook content exceeds 100 MiB.")
    project_tag_sets = await client.get(
        "notebook",
        f"/projects/{project_id}/tags",
        RECORD_TAG_SETS,
        organization_id=principal.organization_id,
    )
    tags_by_record = {
        (record.entity_type, record.entity_id): record.tags
        for record in project_tag_sets
    }

    if format == "json":
        export_data = {
            "format_version": 1,
            "project": project.model_dump(mode="json"),
            "tasks": [task.model_dump(mode="json") for task in tasks],
            "experiments": [
                {
                    "experiment": experiment.model_dump(mode="json"),
                    "tags": tags_by_record.get(("experiment", experiment.id), []),
                    "entries": [
                        {
                            **entry.model_dump(mode="json"),
                            "tags": tags_by_record.get(("entry", entry.id), []),
                        }
                        for entry in entries
                    ],
                }
                for experiment, entries in zip(experiments, entries_by_experiment)
            ],
        }
        content = json.dumps(export_data, indent=2, ensure_ascii=False)
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="eln-project-{project_id}.json"'
                )
            },
        )

    if format == "zip":
        attachments_by_entry: dict[int, list[AttachmentRead]] = {}
        total_attachment_bytes = 0
        attachment_count = 0
        for entries in entries_by_experiment:
            for entry in entries:
                attachments = await client.get(
                    "notebook",
                    f"/entries/{entry.id}/attachments",
                    ATTACHMENTS,
                    organization_id=principal.organization_id,
                )
                attachment_count += len(attachments)
                total_attachment_bytes += sum(item.size_bytes for item in attachments)
                if attachment_count > 5000:
                    raise HTTPException(status_code=413, detail="Project contains too many attachments to export.")
                attachments_by_entry[entry.id] = attachments
        if total_content_bytes + total_attachment_bytes > 100 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Project export exceeds 100 MiB.")
        bundle = io.BytesIO()
        with ZipFile(bundle, "w", compression=ZIP_DEFLATED) as archive:
            records = []
            for experiment, entries in zip(experiments, entries_by_experiment):
                exported_entries = []
                for entry in entries:
                    exported_attachments = []
                    for attachment in attachments_by_entry[entry.id]:
                        archive_path = (
                            f"attachments/entry-{entry.id}/"
                            f"{attachment.id}-{PurePosixPath(attachment.original_filename).name}"
                        )
                        exported_attachments.append(
                            {
                                **attachment.model_dump(mode="json"),
                                "archive_path": archive_path,
                            }
                        )
                    exported_entries.append(
                        {
                            **entry.model_dump(mode="json"),
                            "tags": tags_by_record.get(("entry", entry.id), []),
                            "attachments": exported_attachments,
                        }
                    )
                records.append(
                    {
                        "experiment": experiment.model_dump(mode="json"),
                        "tags": tags_by_record.get(("experiment", experiment.id), []),
                        "entries": exported_entries,
                    }
                )
            archive.writestr(
                "project.json",
                json.dumps(
                    {
                        "format_version": 1,
                        "project": project.model_dump(mode="json"),
                        "tasks": [task.model_dump(mode="json") for task in tasks],
                        "experiments": records,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
            )
            for attachments in attachments_by_entry.values():
                for attachment in attachments:
                    content = await client.get_bytes(
                        "notebook",
                        f"/attachments/{attachment.id}/content",
                        organization_id=principal.organization_id,
                    )
                    if len(content) != attachment.size_bytes:
                        raise HTTPException(
                            status_code=502,
                            detail=f"Attachment {attachment.id} size did not match its metadata.",
                        )
                    archive_path = (
                        f"attachments/entry-{attachment.entry_id}/"
                        f"{attachment.id}-{PurePosixPath(attachment.original_filename).name}"
                    )
                    archive.writestr(archive_path, content)
        return Response(
            content=bundle.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="eln-project-{project_id}.zip"'
                )
            },
        )

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "project_id",
            "project_name",
            "experiment_id",
            "experiment_name",
            "experiment_status",
            "experiment_tags",
            "entry_id",
            "entry_title",
            "entry_content",
            "entry_tags",
            "entry_created_at",
            "entry_updated_at",
        ]
    )
    for experiment, entries in zip(experiments, entries_by_experiment):
        for entry in entries:
            writer.writerow(
                [
                    project.id,
                    project.name,
                    experiment.id,
                    experiment.name,
                    experiment.status,
                    ", ".join(tags_by_record.get(("experiment", experiment.id), [])),
                    entry.id,
                    entry.title,
                    entry.content,
                    ", ".join(tags_by_record.get(("entry", entry.id), [])),
                    entry.created_at.isoformat(),
                    entry.updated_at.isoformat(),
                ]
            )
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="eln-project-{project_id}.csv"'
            )
        },
    )


@projects_router.post(
    "/{project_id}/import",
    response_model=ProjectImportResult,
    status_code=201,
)
async def import_project_records(
    project_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
    file: UploadFile = File(...),
) -> ProjectImportResult:
    await _require_project_access(client, principal, project_id, write=True)
    chunks: list[bytes] = []
    request_size = 0
    try:
        while chunk := await file.read(1024 * 1024):
            request_size += len(chunk)
            if request_size > 105 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Import bundle exceeds 105 MiB.")
            chunks.append(chunk)
    finally:
        await file.close()
    raw = b"".join(chunks)
    archive: ZipFile | None = None
    archive_members: dict[str, ZipInfo] = {}
    if raw.startswith(b"PK"):
        try:
            archive = ZipFile(io.BytesIO(raw))
            infos = archive.infolist()
            if len(infos) > 5001 or sum(info.file_size for info in infos) > 105 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Import archive exceeds its size limits.")
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise HTTPException(status_code=422, detail="Import archive contains duplicate paths.")
            archive_members = {info.filename: info for info in infos}
            if archive_members["project.json"].file_size > 20 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Project metadata exceeds 20 MiB.")
            project_json = archive.read("project.json")
        except (BadZipFile, KeyError, OSError, RuntimeError) as error:
            raise HTTPException(status_code=422, detail="Import ZIP must contain a valid project.json.") from error
    else:
        project_json = raw
        if len(project_json) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Project JSON exceeds 20 MiB.")
    try:
        payload = ProjectImportPayload.model_validate_json(project_json)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error

    total_entries = sum(len(item.entries) for item in payload.experiments)
    source_experiment_ids = [
        item.experiment.id
        for item in payload.experiments
        if item.experiment.id is not None
    ]
    source_experiment_id_set = set(source_experiment_ids)
    if len(source_experiment_ids) != len(set(source_experiment_ids)):
        raise HTTPException(status_code=422, detail="Import contains duplicate experiment IDs.")
    if any(
        task.experiment_id is not None
        and task.experiment_id not in source_experiment_id_set
        for task in payload.tasks
    ):
        raise HTTPException(status_code=422, detail="A task references an experiment missing from the import.")
    total_content_bytes = sum(
        len(entry.content.encode("utf-8"))
        for experiment in payload.experiments
        for entry in experiment.entries
    ) + sum(len(task.description.encode("utf-8")) for task in payload.tasks)
    attachment_paths = [
        attachment.archive_path
        for experiment in payload.experiments
        for entry in experiment.entries
        for attachment in entry.attachments
    ]
    if total_entries > 5000 or total_content_bytes > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Project data exceeds import limits.")
    if archive is None and attachment_paths:
        raise HTTPException(status_code=422, detail="Attachments require a ZIP project export.")
    imported_attachment_bytes: dict[str, bytes] = {}
    if archive is not None:
        expected_paths = {"project.json", *attachment_paths}
        if len(attachment_paths) != len(set(attachment_paths)):
            raise HTTPException(status_code=422, detail="Import references duplicate attachment paths.")
        if set(archive_members) != expected_paths:
            raise HTTPException(status_code=422, detail="Import archive contains missing or unreferenced files.")
        for path in attachment_paths:
            parts = PurePosixPath(path).parts
            if (
                "\\" in path
                or PurePosixPath(path).is_absolute()
                or ".." in parts
                or not path.startswith("attachments/entry-")
            ):
                raise HTTPException(status_code=422, detail="Import archive contains an unsafe attachment path.")
            info = archive_members[path]
            if info.file_size > 25 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="An imported attachment exceeds 25 MiB.")
        if sum(archive_members[path].file_size for path in attachment_paths) + total_content_bytes > 100 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Project import exceeds 100 MiB of content.")
        try:
            for path in attachment_paths:
                info = archive_members[path]
                if info.is_dir() or info.external_attr >> 16 & 0o170000 == 0o120000:
                    raise HTTPException(status_code=422, detail="Import archive contains an invalid attachment entry.")
                content = archive.read(path)
                if len(content) != info.file_size:
                    raise HTTPException(status_code=422, detail="Imported attachment size is inconsistent.")
                imported_attachment_bytes[path] = content
        except (BadZipFile, RuntimeError, OSError) as error:
            raise HTTPException(status_code=422, detail="Import archive contains an unreadable attachment.") from error

    await client.get(
        "projects",
        f"/projects/{project_id}",
        PROJECT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )
    imported_experiments = 0
    imported_entries = 0
    imported_attachments = 0
    imported_tasks = 0
    imported_experiment_ids: dict[int, int] = {}
    for experiment_data in payload.experiments:
        experiment = await client.post(
            "notebook",
            f"/projects/{project_id}/experiments",
            {
                "name": experiment_data.experiment.name,
                "description": experiment_data.experiment.description,
            },
            EXPERIMENT,
            organization_id=principal.organization_id,
        )
        imported_experiments += 1
        source_experiment_id = experiment_data.experiment.id
        if source_experiment_id is not None:
            imported_experiment_ids[source_experiment_id] = experiment.id
        if experiment_data.experiment.status != "in_progress":
            experiment = await client.patch(
                "notebook",
                f"/experiments/{experiment.id}/status",
                {"status": experiment_data.experiment.status},
                EXPERIMENT,
                organization_id=principal.organization_id,
                user_id=principal.user_id,
            )
        if experiment_data.tags:
            await client.put(
                "notebook",
                f"/records/experiment/{experiment.id}/tags",
                {"entity_type": "experiment", "tags": experiment_data.tags},
                RECORD_TAG_SET,
                organization_id=principal.organization_id,
                user_id=principal.user_id,
            )
        for entry_data in experiment_data.entries:
            entry = await client.post(
                "notebook",
                f"/experiments/{experiment.id}/entries",
                {"title": entry_data.title, "content": entry_data.content},
                ENTRY,
                organization_id=principal.organization_id,
            )
            imported_entries += 1
            if entry_data.tags:
                await client.put(
                    "notebook",
                    f"/records/entry/{entry.id}/tags",
                    {"entity_type": "entry", "tags": entry_data.tags},
                    RECORD_TAG_SET,
                    organization_id=principal.organization_id,
                    user_id=principal.user_id,
                )
            for attachment in entry_data.attachments:
                attachment_bytes = imported_attachment_bytes[attachment.archive_path]
                await client.post_bytes(
                    "notebook",
                    f"/entries/{entry.id}/attachments?filename={quote(attachment.original_filename, safe='')}",
                    attachment_bytes,
                    ATTACHMENT,
                    organization_id=principal.organization_id,
                    user_id=principal.user_id,
                    content_type=attachment.media_type,
                )
                imported_attachments += 1
    for task_data in payload.tasks:
        task = await client.post(
            "notebook",
            f"/projects/{project_id}/tasks",
            {
                "project_id": project_id,
                "experiment_id": (
                    imported_experiment_ids.get(task_data.experiment_id)
                    if task_data.experiment_id is not None
                    else None
                ),
                "assigned_to_user_id": None,
                "title": task_data.title,
                "description": task_data.description,
                "due_at": task_data.due_at.isoformat() if task_data.due_at else None,
                "priority": task_data.priority,
            },
            TASK,
            organization_id=principal.organization_id,
            user_id=principal.user_id,
        )
        imported_tasks += 1
        if task_data.status != "open":
            await client.patch(
                "notebook",
                f"/tasks/{task.id}/status",
                {"status": task_data.status},
                TASK,
                organization_id=principal.organization_id,
                user_id=principal.user_id,
            )
    return ProjectImportResult(
        project_id=project_id,
        experiments_imported=imported_experiments,
        entries_imported=imported_entries,
        attachments_imported=imported_attachments,
        tasks_imported=imported_tasks,
    )


@projects_router.get("/{project_id}/members", response_model=list[ProjectMemberRead])
async def list_project_members(
    project_id: int, client: ServiceClientDep, principal: PrincipalDep
) -> list[ProjectMemberRead]:
    return await client.get(
        "projects",
        f"/projects/{project_id}/members",
        PROJECT_MEMBERS,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@projects_router.put(
    "/{project_id}/members/{user_id}", response_model=ProjectMemberRead
)
async def set_project_member(
    project_id: int,
    user_id: int,
    payload: ProjectMemberCreate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> ProjectMemberRead:
    if payload.user_id != user_id:
        raise HTTPException(status_code=422, detail="Path user ID must match payload.")
    return await client.put(
        "projects",
        f"/projects/{project_id}/members/{user_id}",
        payload.model_dump(),
        PROJECT_MEMBER,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@projects_router.delete("/{project_id}/members/{user_id}", status_code=204)
async def remove_project_member(
    project_id: int,
    user_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> None:
    await client.delete(
        "projects",
        f"/projects/{project_id}/members/{user_id}",
        TypeAdapter(type(None)),
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@notebook_router.get(
    "/api/projects/{project_id}/experiments",
    response_model=list[ExperimentRead],
)
async def list_experiments(
    project_id: int, client: ServiceClientDep, principal: PrincipalDep
) -> list[ExperimentRead]:
    await _require_project_access(client, principal, project_id)
    return await client.get(
        "notebook", f"/projects/{project_id}/experiments", EXPERIMENT_LIST,
        organization_id=principal.organization_id,
    )


@notebook_router.post(
    "/api/projects/{project_id}/experiments",
    response_model=ExperimentRead,
    status_code=201,
)
async def create_experiment(
    project_id: int,
    payload: ExperimentCreate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> ExperimentRead:
    await _require_project_access(client, principal, project_id, write=True)
    return await client.post(
        "notebook",
        f"/projects/{project_id}/experiments",
        payload.model_dump(),
        EXPERIMENT,
        organization_id=principal.organization_id,
    )


@notebook_router.get(
    "/api/experiments/{experiment_id}/entries",
    response_model=list[EntryRead],
)
async def list_entries(
    experiment_id: int, client: ServiceClientDep, principal: PrincipalDep
) -> list[EntryRead]:
    experiment = await client.get(
        "notebook",
        f"/experiments/{experiment_id}",
        EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id)
    return await client.get(
        "notebook", f"/experiments/{experiment_id}/entries", ENTRY_LIST,
        organization_id=principal.organization_id,
    )


@notebook_router.patch(
    "/api/experiments/{experiment_id}/status",
    response_model=ExperimentRead,
)
async def update_experiment_status(
    experiment_id: int,
    payload: ExperimentStatusUpdate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> ExperimentRead:
    experiment = await client.get(
        "notebook",
        f"/experiments/{experiment_id}",
        EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id, write=True)
    return await client.patch(
        "notebook",
        f"/experiments/{experiment_id}/status",
        payload.model_dump(mode="json"),
        EXPERIMENT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )


@notebook_router.post(
    "/api/experiments/{experiment_id}/entries",
    response_model=EntryRead,
    status_code=201,
)
async def create_entry(
    experiment_id: int,
    payload: EntryCreate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> EntryRead:
    experiment = await client.get(
        "notebook",
        f"/experiments/{experiment_id}",
        EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id, write=True)
    return await client.post(
        "notebook",
        f"/experiments/{experiment_id}/entries",
        payload.model_dump(),
        ENTRY,
        organization_id=principal.organization_id,
    )


@notebook_router.put("/api/entries/{entry_id}", response_model=EntryRead)
async def update_entry(
    entry_id: int,
    payload: EntryUpdate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> EntryRead:
    entry = await client.get(
        "notebook",
        f"/entries/{entry_id}",
        ENTRY,
        organization_id=principal.organization_id,
    )
    experiment = await client.get(
        "notebook",
        f"/experiments/{entry.experiment_id}",
        EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id, write=True)
    return await client.put(
        "notebook", f"/entries/{entry_id}", payload.model_dump(), ENTRY,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )


@notebook_router.get(
    "/api/entries/{entry_id}/revisions",
    response_model=list[EntryRevisionRead],
)
async def list_entry_revisions(
    entry_id: int, client: ServiceClientDep, principal: PrincipalDep
) -> list[EntryRevisionRead]:
    entry = await client.get(
        "notebook", f"/entries/{entry_id}", ENTRY,
        organization_id=principal.organization_id,
    )
    experiment = await client.get(
        "notebook", f"/experiments/{entry.experiment_id}", EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id)
    return await client.get(
        "notebook", f"/entries/{entry_id}/revisions", ENTRY_REVISIONS,
        organization_id=principal.organization_id,
    )


@notebook_router.post(
    "/api/entries/{entry_id}/revisions/{revision_id}/restore",
    response_model=EntryRead,
)
async def restore_entry_revision(
    entry_id: int,
    revision_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> EntryRead:
    entry = await client.get(
        "notebook", f"/entries/{entry_id}", ENTRY,
        organization_id=principal.organization_id,
    )
    experiment = await client.get(
        "notebook", f"/experiments/{entry.experiment_id}", EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id, write=True)
    return await client.post(
        "notebook",
        f"/entries/{entry_id}/revisions/{revision_id}/restore",
        {},
        ENTRY,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )


async def _tagged_record_project_id(
    entity_type: Literal[
        "experiment", "entry", "inventory", "sample", "equipment", "template"
    ],
    entity_id: int,
    client: ServiceClient,
    organization_id: int,
) -> int:
    if entity_type == "experiment":
        experiment = await client.get(
            "notebook",
            f"/experiments/{entity_id}",
            EXPERIMENT,
            organization_id=organization_id,
        )
        return experiment.project_id
    if entity_type in {"inventory", "sample", "equipment", "template"}:
        resource = await client.get(
            "notebook",
            f"/resources/{entity_type}/{entity_id}",
            TypeAdapter(
                {
                    "inventory": InventoryItemRead,
                    "sample": SampleRead,
                    "equipment": EquipmentRead,
                    "template": NotebookTemplateRead,
                }[entity_type]
            ),
            organization_id=organization_id,
        )
        return resource.project_id or 0 if entity_type == "sample" else 0
    entry = await client.get(
        "notebook",
        f"/entries/{entity_id}",
        ENTRY,
        organization_id=organization_id,
    )
    experiment = await client.get(
        "notebook",
        f"/experiments/{entry.experiment_id}",
        EXPERIMENT,
        organization_id=organization_id,
    )
    return experiment.project_id


@notebook_router.get(
    "/api/records/{entity_type}/{entity_id}/tags",
    response_model=RecordTagSetRead,
)
async def get_record_tags(
    entity_type: Literal[
        "experiment", "entry", "inventory", "sample", "equipment", "template"
    ],
    entity_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> RecordTagSetRead:
    project_id = await _tagged_record_project_id(
        entity_type, entity_id, client, principal.organization_id
    )
    if project_id:
        await _require_project_access(client, principal, project_id)
    return await client.get(
        "notebook",
        f"/records/{entity_type}/{entity_id}/tags",
        RECORD_TAG_SET,
        organization_id=principal.organization_id,
    )


@notebook_router.put(
    "/api/records/{entity_type}/{entity_id}/tags",
    response_model=RecordTagSetRead,
)
async def replace_record_tags(
    entity_type: Literal[
        "experiment", "entry", "inventory", "sample", "equipment", "template"
    ],
    entity_id: int,
    payload: RecordTagSetUpdate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> RecordTagSetRead:
    if payload.entity_type != entity_type:
        raise HTTPException(status_code=422, detail="Tagged record type mismatch.")
    project_id = await _tagged_record_project_id(
        entity_type, entity_id, client, principal.organization_id
    )
    if project_id:
        await _require_project_access(client, principal, project_id, write=True)
    return await client.put(
        "notebook",
        f"/records/{entity_type}/{entity_id}/tags",
        payload.model_dump(mode="json"),
        RECORD_TAG_SET,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )


@notebook_router.get(
    "/api/projects/{project_id}/tasks", response_model=list[TaskRead]
)
async def list_project_tasks(
    project_id: int, client: ServiceClientDep, principal: PrincipalDep
) -> list[TaskRead]:
    await _require_project_access(client, principal, project_id)
    return await client.get(
        "notebook",
        f"/projects/{project_id}/tasks",
        TASK_LIST,
        organization_id=principal.organization_id,
    )


@notebook_router.post(
    "/api/projects/{project_id}/tasks", response_model=TaskRead, status_code=201
)
async def create_project_task(
    project_id: int,
    payload: TaskCreate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> TaskRead:
    if payload.project_id != project_id:
        raise HTTPException(status_code=422, detail="Task project does not match the request.")
    await _require_project_access(client, principal, project_id, write=True)
    return await client.post(
        "notebook",
        f"/projects/{project_id}/tasks",
        payload.model_dump(mode="json"),
        TASK,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )


@notebook_router.patch("/api/tasks/{task_id}/status", response_model=TaskRead)
async def update_project_task_status(
    task_id: int,
    payload: TaskStatusUpdate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> TaskRead:
    task = await client.get(
        "notebook", f"/tasks/{task_id}", TASK,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, task.project_id, write=True)
    return await client.patch(
        "notebook",
        f"/tasks/{task_id}/status",
        payload.model_dump(),
        TASK,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )


@notebook_router.post(
    "/api/entries/{entry_id}/signatures",
    response_model=RecordSignatureRead,
    status_code=201,
)
async def create_entry_signature(
    entry_id: int,
    payload: RecordSignatureCreate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> RecordSignatureRead:
    entry = await client.get(
        "notebook", f"/entries/{entry_id}", ENTRY,
        organization_id=principal.organization_id,
    )
    experiment = await client.get(
        "notebook", f"/experiments/{entry.experiment_id}", EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id, write=True)
    return await client.post(
        "notebook",
        f"/entries/{entry_id}/signatures",
        payload.model_dump(mode="json"),
        SIGNATURE,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )


@notebook_router.get(
    "/api/entries/{entry_id}/signatures",
    response_model=list[RecordSignatureRead],
)
async def list_entry_signatures(
    entry_id: int, client: ServiceClientDep, principal: PrincipalDep
) -> list[RecordSignatureRead]:
    entry = await client.get(
        "notebook", f"/entries/{entry_id}", ENTRY,
        organization_id=principal.organization_id,
    )
    experiment = await client.get(
        "notebook", f"/experiments/{entry.experiment_id}", EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id)
    return await client.get(
        "notebook",
        f"/entries/{entry_id}/signatures",
        SIGNATURE_LIST,
        organization_id=principal.organization_id,
    )


@activity_router.get("/audit/verify", response_model=AuditVerificationRead)
async def verify_audit_chain(
    client: ServiceClientDep, principal: PrincipalDep
) -> AuditVerificationRead:
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="Organization admin role required.")
    return await client.get(
        "notebook",
        "/audit/verify",
        AUDIT_VERIFICATION,
        organization_id=principal.organization_id,
    )


@inventory_router.patch(
    "/resources/{entity_type}/{entity_id}/status",
    response_model=InventoryItemRead | SampleRead | EquipmentRead | NotebookTemplateRead,
)
async def update_resource_status(
    entity_type: Literal["inventory", "sample", "equipment", "template"],
    entity_id: int,
    payload: ResourceStatusUpdate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> InventoryItemRead | SampleRead | EquipmentRead | NotebookTemplateRead:
    if entity_type == "sample":
        sample = await client.get(
            "notebook", f"/samples/{entity_id}", SAMPLE,
            organization_id=principal.organization_id,
        )
        if sample.project_id is not None:
            await _require_project_access(client, principal, sample.project_id, write=True)
        elif principal.role != "admin":
            raise HTTPException(status_code=403, detail="Organization admin role required.")
    elif entity_type == "equipment" and principal.role != "admin":
        raise HTTPException(status_code=403, detail="Organization admin role required.")
    elif entity_type == "template" and principal.role != "admin":
        raise HTTPException(status_code=403, detail="Organization admin role required.")
    return await client.patch(
        "notebook",
        f"/resources/{entity_type}/{entity_id}/status",
        payload.model_dump(),
        TypeAdapter(
            {
                "inventory": InventoryItemRead,
                "sample": SampleRead,
                "equipment": EquipmentRead,
                "template": NotebookTemplateRead,
            }[entity_type]
        ),
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@inventory_router.get("/inventory", response_model=list[InventoryItemRead])
async def list_inventory(
    client: ServiceClientDep, principal: PrincipalDep
) -> list[InventoryItemRead]:
    return await client.get(
        "notebook",
        "/inventory",
        INVENTORY_LIST,
        organization_id=principal.organization_id,
    )


@inventory_router.post(
    "/inventory", response_model=InventoryItemRead, status_code=201
)
async def create_inventory_item(
    payload: InventoryItemCreate, client: ServiceClientDep, principal: PrincipalDep
) -> InventoryItemRead:
    return await client.post(
        "notebook",
        "/inventory",
        payload.model_dump(mode="json"),
        INVENTORY_ITEM,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )


@inventory_router.get(
    "/inventory/{item_id}/movements",
    response_model=list[StockMovementRead],
)
async def list_stock_movements(
    item_id: int, client: ServiceClientDep, principal: PrincipalDep
) -> list[StockMovementRead]:
    return await client.get(
        "notebook",
        f"/inventory/{item_id}/movements",
        STOCK_MOVEMENTS,
        organization_id=principal.organization_id,
    )


@inventory_router.post(
    "/inventory/{item_id}/adjustments",
    response_model=StockMovementRead,
    status_code=201,
)
async def adjust_stock(
    item_id: int,
    payload: StockAdjustment,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> StockMovementRead:
    return await client.post(
        "notebook",
        f"/inventory/{item_id}/adjustments",
        payload.model_dump(mode="json"),
        STOCK_MOVEMENT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )


@inventory_router.get("/samples", response_model=list[SampleRead])
async def list_samples(
    client: ServiceClientDep, principal: PrincipalDep
) -> list[SampleRead]:
    samples = await client.get(
        "notebook",
        "/samples",
        SAMPLE_LIST,
        organization_id=principal.organization_id,
    )
    if principal.role == "admin":
        return samples
    projects = await client.get(
        "projects",
        "/projects",
        PROJECT_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )
    accessible_project_ids = {project.id for project in projects}
    return [
        sample
        for sample in samples
        if sample.project_id is None or sample.project_id in accessible_project_ids
    ]


@inventory_router.post("/samples", response_model=SampleRead, status_code=201)
async def create_sample(
    payload: SampleCreate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> SampleRead:
    if payload.project_id is not None:
        await _require_project_access(client, principal, payload.project_id, write=True)
    return await client.post(
        "notebook",
        "/samples",
        payload.model_dump(mode="json"),
        SAMPLE,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )


@templates_router.get("/templates", response_model=list[NotebookTemplateRead])
async def list_templates(
    client: ServiceClientDep, principal: PrincipalDep
) -> list[NotebookTemplateRead]:
    return await client.get(
        "notebook",
        "/templates",
        TEMPLATE_LIST,
        organization_id=principal.organization_id,
    )


@templates_router.post("/templates", response_model=NotebookTemplateRead, status_code=201)
async def create_template(
    payload: NotebookTemplateCreate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> NotebookTemplateRead:
    return await client.post(
        "notebook",
        "/templates",
        payload.model_dump(mode="json"),
        TEMPLATE,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )


@templates_router.put("/templates/{template_id}", response_model=NotebookTemplateRead)
async def update_template(
    template_id: int,
    payload: NotebookTemplateUpdate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> NotebookTemplateRead:
    return await client.put(
        "notebook",
        f"/templates/{template_id}",
        payload.model_dump(mode="json"),
        TEMPLATE,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )


@templates_router.post("/entries/{entry_id}/apply-template", response_model=EntryRead)
async def apply_entry_template(
    entry_id: int,
    template_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> EntryRead:
    entry = await client.get(
        "notebook",
        f"/entries/{entry_id}",
        ENTRY,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
    )
    experiment = await client.get(
        "notebook",
        f"/experiments/{entry.experiment_id}",
        EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id, write=True)
    return await client.post(
        "notebook",
        f"/entries/{entry_id}/apply-template?template_id={template_id}",
        {},
        ENTRY,
        organization_id=principal.organization_id,
    )


@templates_router.post(
    "/projects/{project_id}/experiments/from-protocol",
    response_model=ExperimentRead,
    status_code=201,
)
async def create_experiment_from_protocol(
    project_id: int,
    template_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> ExperimentRead:
    await _require_project_access(client, principal, project_id, write=True)
    return await client.post(
        "notebook",
        f"/projects/{project_id}/experiments/from-protocol?template_id={template_id}",
        {},
        EXPERIMENT,
        organization_id=principal.organization_id,
    )


@attachments_router.get(
    "/entries/{entry_id}/attachments",
    response_model=list[AttachmentRead],
)
async def list_entry_attachments(
    entry_id: int, client: ServiceClientDep, principal: PrincipalDep
) -> list[AttachmentRead]:
    entry = await client.get(
        "notebook", f"/entries/{entry_id}", ENTRY,
        organization_id=principal.organization_id,
    )
    experiment = await client.get(
        "notebook", f"/experiments/{entry.experiment_id}", EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id)
    return await client.get(
        "notebook", f"/entries/{entry_id}/attachments", ATTACHMENTS,
        organization_id=principal.organization_id,
    )


@attachments_router.post(
    "/entries/{entry_id}/attachments",
    response_model=AttachmentRead,
    status_code=201,
)
async def upload_entry_attachment(
    entry_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
    file: UploadFile = File(...),
) -> AttachmentRead:
    entry = await client.get(
        "notebook", f"/entries/{entry_id}", ENTRY,
        organization_id=principal.organization_id,
    )
    experiment = await client.get(
        "notebook", f"/experiments/{entry.experiment_id}", EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id, write=True)
    parts: list[bytes] = []
    size = 0
    try:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > 25 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Attachment exceeds 25 MiB.")
            parts.append(chunk)
    finally:
        await file.close()
    filename = quote(file.filename or "", safe="")
    return await client.post_bytes(
        "notebook",
        f"/entries/{entry_id}/attachments?filename={filename}",
        b"".join(parts),
        ATTACHMENT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        content_type=file.content_type or "application/octet-stream",
    )


@attachments_router.get("/attachments/{attachment_id}/download")
async def download_entry_attachment(
    attachment_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> Response:
    attachment = await client.get(
        "notebook", f"/attachments/{attachment_id}", ATTACHMENT,
        organization_id=principal.organization_id,
    )
    entry = await client.get(
        "notebook", f"/entries/{attachment.entry_id}", ENTRY,
        organization_id=principal.organization_id,
    )
    experiment = await client.get(
        "notebook", f"/experiments/{entry.experiment_id}", EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id)
    content = await client.get_bytes(
        "notebook",
        f"/attachments/{attachment_id}/content",
        organization_id=principal.organization_id,
    )
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(attachment.original_filename)}"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@attachments_router.get("/entries/{entry_id}/export")
async def export_entry_bundle(
    entry_id: int, client: ServiceClientDep, principal: PrincipalDep
) -> Response:
    entry = await client.get(
        "notebook", f"/entries/{entry_id}", ENTRY,
        organization_id=principal.organization_id,
    )
    experiment = await client.get(
        "notebook", f"/experiments/{entry.experiment_id}", EXPERIMENT,
        organization_id=principal.organization_id,
    )
    await _require_project_access(client, principal, experiment.project_id)
    attachments = await client.get(
        "notebook", f"/entries/{entry_id}/attachments", ATTACHMENTS,
        organization_id=principal.organization_id,
    )
    total_bytes = sum(attachment.size_bytes for attachment in attachments)
    if total_bytes > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Entry attachments exceed 100 MiB.")
    bundle = io.BytesIO()
    with ZipFile(bundle, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "entry.json",
            json.dumps(
                {
                    "experiment": experiment.model_dump(mode="json"),
                    "entry": entry.model_dump(mode="json"),
                    "attachments": [
                        attachment.model_dump(mode="json")
                        for attachment in attachments
                    ],
                },
                indent=2,
            ),
        )
        for attachment in attachments:
            content = await client.get_bytes(
                "notebook",
                f"/attachments/{attachment.id}/content",
                organization_id=principal.organization_id,
            )
            archive.writestr(
                f"attachments/{attachment.id}-{attachment.original_filename}",
                content,
            )
    return Response(
        content=bundle.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="eln-entry-{entry_id}.zip"'
        },
    )


@search_router.get("/search", response_model=list[SearchHit])
async def search_records(
    query: str,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> list[SearchHit]:
    normalized = query.strip()
    if len(normalized) < 2 or len(normalized) > 100:
        raise HTTPException(
            status_code=422,
            detail="Search query must contain between 2 and 100 characters.",
        )
    encoded_query = quote(normalized, safe="")
    hits = await client.get(
        "notebook",
        f"/search?query={encoded_query}",
        SEARCH_HITS,
        organization_id=principal.organization_id,
    )
    projects = await client.get(
        "projects",
        "/projects",
        PROJECT_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )
    accessible_projects = {project.id: project for project in projects}
    lowered = normalized.casefold()
    project_hits = [
        SearchHit(
            entity_type="project",
            entity_id=project.id,
            title=project.name,
            detail=project.description,
        )
        for project in projects
        if lowered in project.name.casefold() or lowered in project.description.casefold()
    ]
    permitted_hits = [
        hit
        for hit in hits
        if hit.project_id is None or hit.project_id in accessible_projects
    ]
    return (project_hits + permitted_hits)[:200]


@booking_router.get("/equipment", response_model=list[EquipmentRead])
async def list_equipment(
    client: ServiceClientDep, principal: PrincipalDep
) -> list[EquipmentRead]:
    return await client.get(
        "notebook",
        "/equipment",
        EQUIPMENT_LIST,
        organization_id=principal.organization_id,
    )


@booking_router.post("/equipment", response_model=EquipmentRead, status_code=201)
async def create_equipment(
    payload: EquipmentCreate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> EquipmentRead:
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="Organization admin role required.")
    return await client.post(
        "notebook",
        "/equipment",
        payload.model_dump(),
        EQUIPMENT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@booking_router.get("/equipment/bookings", response_model=list[EquipmentBookingRead])
async def list_equipment_bookings(
    client: ServiceClientDep, principal: PrincipalDep
) -> list[EquipmentBookingRead]:
    bookings = await client.get(
        "notebook",
        "/bookings",
        BOOKINGS,
        organization_id=principal.organization_id,
    )
    if principal.role == "admin":
        return bookings
    projects = await client.get(
        "projects",
        "/projects",
        PROJECT_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )
    accessible = {project.id for project in projects}
    return [
        booking
        for booking in bookings
        if booking.project_id is None or booking.project_id in accessible
    ]


@booking_router.post(
    "/equipment/{equipment_id}/bookings",
    response_model=EquipmentBookingRead,
    status_code=201,
)
async def create_equipment_booking(
    equipment_id: int,
    payload: EquipmentBookingCreate,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> EquipmentBookingRead:
    if payload.project_id is not None:
        await _require_project_access(client, principal, payload.project_id, write=True)
    return await client.post(
        "notebook",
        f"/equipment/{equipment_id}/bookings",
        payload.model_dump(mode="json"),
        BOOKING,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@booking_router.post(
    "/equipment/bookings/{booking_id}/cancel",
    response_model=EquipmentBookingRead,
)
async def cancel_equipment_booking(
    booking_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> EquipmentBookingRead:
    return await client.post(
        "notebook",
        f"/bookings/{booking_id}/cancel",
        {},
        BOOKING,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@activity_router.get("/activity", response_model=list[ActivityEventRead])
async def list_activity(
    client: ServiceClientDep, principal: PrincipalDep
) -> list[ActivityEventRead]:
    events = await client.get(
        "activity", "/activity", ACTIVITY_LIST,
        organization_id=principal.organization_id,
    )
    if principal.role == "admin":
        return events
    accessible_projects = await client.get(
        "projects",
        "/projects",
        PROJECT_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )
    project_ids = {project.id for project in accessible_projects}
    visible_events: list[ActivityEventRead] = []
    for event in events:
        project_id = event.entity_id if event.entity_type == "project" else None
        if project_id is None:
            try:
                project_id = int(event.details["project_id"])
            except (KeyError, ValueError):
                continue
        if project_id in project_ids:
            visible_events.append(event)
    return visible_events


async def _require_project_access(
    client: ServiceClient,
    principal: Principal,
    project_id: int,
    *,
    write: bool = False,
) -> ProjectAccessRead:
    access = await client.get(
        "projects",
        f"/projects/{project_id}/access",
        PROJECT_ACCESS,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )
    if write and access.role not in {"admin", "owner", "editor"}:
        raise HTTPException(status_code=403, detail="Project editor access required.")
    return access
