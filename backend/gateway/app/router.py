import io
import json
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import TypeAdapter

from eln_common.contracts import (
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
    SearchHit,
    SampleCreate,
    SampleRead,
    StockAdjustment,
    StockMovementRead,
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
