from typing import Annotated
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
import json
import os
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from eln_common.contracts import (
    AuditVerificationRead,
    AttachmentRead,
    EntryCreate,
    EntryRead,
    EntryRevisionRead,
    EntryUpdate,
    EquipmentBookingCreate,
    EquipmentBookingRead,
    EquipmentCreate,
    EquipmentRead,
    EntryTimestampRead,
    ExperimentCreate,
    ExperimentRead,
    ExperimentStatusUpdate,
    InventoryItemCreate,
    InventoryItemRead,
    NotebookTemplateCreate,
    NotebookTemplateRead,
    NotebookTemplateUpdate,
    RecordTagSetRead,
    RecordTagSetUpdate,
    RecordSignatureCreate,
    RecordSignatureRead,
    SampleCreate,
    SampleRead,
    ResourceStatusUpdate,
    SearchHit,
    StockAdjustment,
    StockMovementRead,
    TaskCreate,
    TaskRead,
    TaskStatusUpdate,
    StorageLocationCreate,
    StorageLocationRead,
    WorkflowRuleCreate,
    WorkflowRuleRead,
)
from eln_common.database import Database
from eln_common.errors import AuthenticationError, InvalidInputError

from .repository import NotebookRepository
from .service import NotebookService


def create_router(database: Database) -> APIRouter:
    router = APIRouter(tags=["notebook"])

    def get_service(db: Annotated[Session, Depends(database.dependency)]) -> NotebookService:
        return NotebookService(NotebookRepository(db), db)

    def actor_headers(
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        user_id: Annotated[int, Header(alias="X-User-ID")],
        organization_role: Annotated[str, Header(alias="X-Organization-Role")] = "member",
    ) -> tuple[int, int, bool]:
        return organization_id, user_id, organization_role == "admin"

    @router.get("/equipment", response_model=list[EquipmentRead])
    def list_equipment(
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[EquipmentRead]:
        return service.list_equipment(organization_id)

    @router.post(
        "/equipment", response_model=EquipmentRead, status_code=status.HTTP_201_CREATED
    )
    def create_equipment(
        payload: EquipmentCreate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> EquipmentRead:
        organization_id, user_id, is_admin = actor
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admin role required.",
            )
        return service.create_equipment(
            organization_id, user_id, payload.model_dump()
        )

    @router.get("/bookings", response_model=list[EquipmentBookingRead])
    def list_bookings(
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[EquipmentBookingRead]:
        return service.list_bookings(organization_id)

    @router.get("/projects/{project_id}/tasks", response_model=list[TaskRead])
    def list_tasks(
        project_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[TaskRead]:
        return service.list_tasks(organization_id, project_id)

    @router.get(
        "/projects/{project_id}/workflow-rules",
        response_model=list[WorkflowRuleRead],
    )
    def list_workflow_rules(
        project_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[WorkflowRuleRead]:
        return service.list_workflow_rules(organization_id, project_id)

    @router.post(
        "/projects/{project_id}/workflow-rules",
        response_model=WorkflowRuleRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_workflow_rule(
        project_id: int,
        payload: WorkflowRuleCreate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> WorkflowRuleRead:
        organization_id, user_id, _ = actor
        if payload.project_id != project_id:
            raise InvalidInputError("Workflow project does not match the request.")
        return service.create_workflow_rule(
            organization_id, user_id, payload.model_dump()
        )

    @router.get(
        "/storage-locations", response_model=list[StorageLocationRead]
    )
    def list_storage_locations(
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[StorageLocationRead]:
        return service.list_storage_locations(organization_id)

    @router.post(
        "/storage-locations",
        response_model=StorageLocationRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_storage_location(
        payload: StorageLocationCreate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> StorageLocationRead:
        organization_id, user_id, is_admin = actor
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admin role required.",
            )
        return service.create_storage_location(
            organization_id, user_id, payload.model_dump()
        )

    @router.post(
        "/entries/{entry_id}/timestamps",
        response_model=EntryTimestampRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_entry_timestamp(
        entry_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> EntryTimestampRead:
        organization_id, user_id, _ = actor
        return service.create_entry_timestamp(organization_id, entry_id, user_id)

    @router.get(
        "/entries/{entry_id}/timestamps",
        response_model=list[EntryTimestampRead],
    )
    def list_entry_timestamps(
        entry_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[EntryTimestampRead]:
        return service.list_entry_timestamps(organization_id, entry_id)

    @router.get(
        "/entries/{entry_id}/timestamps/{timestamp_id}/proof"
    )
    def download_entry_timestamp_proof(
        entry_id: int,
        timestamp_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> Response:
        timestamp = service.get_entry_timestamp(
            organization_id, entry_id, timestamp_id
        )
        certificate_path = os.getenv("ELN_TSA_CERTIFICATE_FILE", "").strip()
        if not certificate_path:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="TSA verification certificate is not configured.",
            )
        try:
            certificate = Path(certificate_path).read_bytes()
        except OSError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="TSA verification certificate could not be read.",
            ) from error
        proof = BytesIO()
        with ZipFile(proof, "w", ZIP_DEFLATED) as archive:
            archive.writestr("snapshot.json", timestamp.snapshot_json)
            archive.writestr("timestamp.tsr", timestamp.token_der)
            archive.writestr("tsa-signer.pem", certificate)
            archive.writestr(
                "proof.json",
                json.dumps(
                    {
                        "format": "RFC3161",
                        "tsa_url": timestamp.tsa_url,
                        "record_sha256": timestamp.record_sha256,
                        "timestamp": timestamp.tsa_time.isoformat(),
                        "verification": (
                            "Verify timestamp.tsr against snapshot.json with "
                            "the included explicitly pinned tsa-signer.pem."
                        ),
                    },
                    indent=2,
                ),
            )
        return Response(
            content=proof.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="entry-{entry_id}-timestamp-{timestamp_id}.zip"'
                ),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.post(
        "/projects/{project_id}/tasks",
        response_model=TaskRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_task(
        project_id: int,
        payload: TaskCreate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> TaskRead:
        organization_id, user_id, _ = actor
        if payload.project_id != project_id:
            raise InvalidInputError("Task project does not match the request.")
        return service.create_task(
            organization_id, user_id, payload.model_dump()
        )

    @router.patch("/tasks/{task_id}/status", response_model=TaskRead)
    def update_task_status(
        task_id: int,
        payload: TaskStatusUpdate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> TaskRead:
        organization_id, user_id, _ = actor
        return service.update_task_status(
            organization_id, task_id, user_id, payload.status
        )

    @router.get("/tasks/{task_id}", response_model=TaskRead)
    def get_task(
        task_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> TaskRead:
        return service.get_task(organization_id, task_id)

    @router.get(
        "/resources/{entity_type}/{entity_id}",
        response_model=InventoryItemRead | SampleRead | EquipmentRead | NotebookTemplateRead,
    )
    def get_resource(
        entity_type: str,
        entity_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ):
        return service.get_resource(organization_id, entity_type, entity_id)

    @router.patch(
        "/resources/{entity_type}/{entity_id}/status",
        response_model=InventoryItemRead | SampleRead | EquipmentRead | NotebookTemplateRead,
    )
    def update_resource_status(
        entity_type: str,
        entity_id: int,
        payload: ResourceStatusUpdate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> InventoryItemRead | SampleRead | EquipmentRead | NotebookTemplateRead:
        organization_id, user_id, _ = actor
        return service.update_resource_status(
            organization_id, entity_type, entity_id, user_id, payload.status
        )

    @router.post(
        "/entries/{entry_id}/signatures",
        response_model=RecordSignatureRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_entry_signature(
        entry_id: int,
        payload: RecordSignatureCreate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> RecordSignatureRead:
        organization_id, user_id, _ = actor
        if payload.entity_id != entry_id:
            raise InvalidInputError("Signature entry does not match the request path.")
        return service.create_signature(
            organization_id, user_id, entry_id, payload.meaning, payload.comment
        )

    @router.get(
        "/entries/{entry_id}/signatures",
        response_model=list[RecordSignatureRead],
    )
    def list_entry_signatures(
        entry_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[RecordSignatureRead]:
        return service.list_signatures(organization_id, entry_id)

    @router.get("/audit/verify", response_model=AuditVerificationRead)
    def verify_audit_chain(
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> AuditVerificationRead:
        return service.verify_audit_chain(organization_id)

    @router.post(
        "/equipment/{equipment_id}/bookings",
        response_model=EquipmentBookingRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_booking(
        equipment_id: int,
        payload: EquipmentBookingCreate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> EquipmentBookingRead:
        organization_id, user_id, _ = actor
        return service.create_booking(
            organization_id, equipment_id, user_id, payload.model_dump()
        )

    @router.post(
        "/bookings/{booking_id}/cancel",
        response_model=EquipmentBookingRead,
    )
    def cancel_booking(
        booking_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> EquipmentBookingRead:
        organization_id, user_id, is_admin = actor
        return service.cancel_booking(organization_id, booking_id, user_id, is_admin)

    @router.get("/inventory", response_model=list[InventoryItemRead])
    def list_inventory(
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[InventoryItemRead]:
        return service.list_inventory(organization_id)

    @router.post(
        "/inventory",
        response_model=InventoryItemRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_inventory_item(
        payload: InventoryItemCreate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> InventoryItemRead:
        organization_id, user_id, _ = actor
        return service.create_inventory_item(
            organization_id, user_id, payload.model_dump()
        )

    @router.get(
        "/inventory/{item_id}/movements",
        response_model=list[StockMovementRead],
    )
    def list_stock_movements(
        item_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[StockMovementRead]:
        return service.list_stock_movements(organization_id, item_id)

    @router.post(
        "/inventory/{item_id}/adjustments",
        response_model=StockMovementRead,
        status_code=status.HTTP_201_CREATED,
    )
    def adjust_stock(
        item_id: int,
        payload: StockAdjustment,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> StockMovementRead:
        organization_id, user_id, _ = actor
        return service.adjust_stock(
            organization_id,
            item_id,
            user_id,
            payload.quantity_delta,
            payload.reason,
        )

    @router.get("/samples", response_model=list[SampleRead])
    def list_samples(
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[SampleRead]:
        return service.list_samples(organization_id)

    @router.get("/templates", response_model=list[NotebookTemplateRead])
    def list_templates(
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[NotebookTemplateRead]:
        return service.list_templates(organization_id)

    @router.get("/search", response_model=list[SearchHit])
    def search_records(
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
        query: str = Query(min_length=2, max_length=100),
    ) -> list[SearchHit]:
        return service.search(organization_id, query)

    @router.post(
        "/templates",
        response_model=NotebookTemplateRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_template(
        payload: NotebookTemplateCreate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> NotebookTemplateRead:
        organization_id, user_id, _ = actor
        return service.create_template(
            organization_id,
            user_id,
            payload.model_dump(mode="json"),
        )

    @router.put("/templates/{template_id}", response_model=NotebookTemplateRead)
    def update_template(
        template_id: int,
        payload: NotebookTemplateUpdate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> NotebookTemplateRead:
        organization_id, user_id, _ = actor
        return service.update_template(
            organization_id,
            template_id,
            user_id,
            payload.model_dump(mode="json"),
        )

    @router.post(
        "/entries/{entry_id}/apply-template",
        response_model=EntryRead,
    )
    def apply_entry_template(
        entry_id: int,
        template_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> EntryRead:
        organization_id, user_id, _ = actor
        return service.apply_entry_template(
            organization_id, entry_id, template_id, user_id
        )

    @router.post(
        "/projects/{project_id}/experiments/from-protocol",
        response_model=ExperimentRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_experiment_from_protocol(
        project_id: int,
        template_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> ExperimentRead:
        experiment, _ = service.create_experiment_from_protocol(
            organization_id, project_id, template_id
        )
        return experiment

    @router.post(
        "/samples", response_model=SampleRead, status_code=status.HTTP_201_CREATED
    )
    def create_sample(
        payload: SampleCreate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> SampleRead:
        organization_id, user_id, _ = actor
        return service.create_sample(
            organization_id, user_id, payload.model_dump()
        )

    @router.get("/projects/{project_id}/experiments", response_model=list[ExperimentRead])
    def list_experiments(
        project_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[ExperimentRead]:
        return service.list_experiments(organization_id, project_id)

    @router.post(
        "/projects/{project_id}/experiments",
        response_model=ExperimentRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_experiment(
        project_id: int,
        payload: ExperimentCreate,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> ExperimentRead:
        return service.create_experiment(
            organization_id, project_id, payload.name, payload.description
        )

    @router.get("/experiments/{experiment_id}/entries", response_model=list[EntryRead])
    def list_entries(
        experiment_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[EntryRead]:
        return service.list_entries(organization_id, experiment_id)

    @router.get("/experiments/{experiment_id}", response_model=ExperimentRead)
    def get_experiment(
        experiment_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> ExperimentRead:
        return service.get_experiment(organization_id, experiment_id)

    @router.patch("/experiments/{experiment_id}/status", response_model=ExperimentRead)
    def update_experiment_status(
        experiment_id: int,
        payload: ExperimentStatusUpdate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> ExperimentRead:
        organization_id, user_id, _ = actor
        return service.update_experiment_status(
            organization_id, experiment_id, user_id, payload.status
        )

    @router.post(
        "/experiments/{experiment_id}/entries",
        response_model=EntryRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_entry(
        experiment_id: int,
        payload: EntryCreate,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> EntryRead:
        return service.create_entry(
            organization_id, experiment_id, payload.title, payload.content
        )

    @router.put("/entries/{entry_id}", response_model=EntryRead)
    def update_entry(
        entry_id: int,
        payload: EntryUpdate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> EntryRead:
        organization_id, user_id, _ = actor
        return service.update_entry(
            organization_id, entry_id, user_id, payload.title, payload.content
        )

    @router.get(
        "/records/{entity_type}/{entity_id}/tags",
        response_model=RecordTagSetRead,
    )
    def get_record_tags(
        entity_type: str,
        entity_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> RecordTagSetRead:
        return service.get_record_tags(organization_id, entity_type, entity_id)

    @router.put(
        "/records/{entity_type}/{entity_id}/tags",
        response_model=RecordTagSetRead,
    )
    def replace_record_tags(
        entity_type: str,
        entity_id: int,
        payload: RecordTagSetUpdate,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> RecordTagSetRead:
        if payload.entity_type != entity_type:
            raise InvalidInputError("Tagged record type does not match the request.")
        organization_id, user_id, _ = actor
        return service.replace_record_tags(
            organization_id,
            entity_type,
            entity_id,
            user_id,
            payload.tags,
        )

    @router.get(
        "/projects/{project_id}/tags",
        response_model=list[RecordTagSetRead],
    )
    def list_project_record_tags(
        project_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[RecordTagSetRead]:
        return service.list_project_record_tags(organization_id, project_id)

    @router.get(
        "/entries/{entry_id}/revisions",
        response_model=list[EntryRevisionRead],
    )
    def list_entry_revisions(
        entry_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[EntryRevisionRead]:
        return service.list_entry_revisions(organization_id, entry_id)

    @router.post(
        "/entries/{entry_id}/revisions/{revision_id}/restore",
        response_model=EntryRead,
    )
    def restore_entry_revision(
        entry_id: int,
        revision_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> EntryRead:
        organization_id, user_id, _ = actor
        return service.restore_entry_revision(
            organization_id, entry_id, revision_id, user_id
        )

    @router.get("/entries/{entry_id}", response_model=EntryRead)
    def get_entry(
        entry_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> EntryRead:
        return service.get_entry(organization_id, entry_id)

    @router.get(
        "/entries/{entry_id}/attachments",
        response_model=list[AttachmentRead],
    )
    def list_attachments(
        entry_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> list[AttachmentRead]:
        return service.list_attachments(organization_id, entry_id)

    @router.post(
        "/entries/{entry_id}/attachments",
        response_model=AttachmentRead,
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_attachment(
        entry_id: int,
        request: Request,
        service: Annotated[NotebookService, Depends(get_service)],
        actor: Annotated[tuple[int, int, bool], Depends(actor_headers)],
    ) -> AttachmentRead:
        organization_id, user_id, _ = actor
        filename = request.query_params.get("filename", "")
        content = await request.body()
        return service.add_attachment(
            organization_id,
            entry_id,
            user_id,
            filename,
            request.headers.get("Content-Type", "application/octet-stream"),
            content,
        )

    @router.get("/attachments/{attachment_id}/content")
    def download_attachment(
        attachment_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> Response:
        attachment = service.get_attachment(organization_id, attachment_id)
        return FileResponse(
            service.attachment_path(attachment),
            media_type="application/octet-stream",
            filename=attachment.original_filename,
            headers={"X-Content-Type-Options": "nosniff"},
        )

    @router.get("/attachments/{attachment_id}", response_model=AttachmentRead)
    def get_attachment(
        attachment_id: int,
        service: Annotated[NotebookService, Depends(get_service)],
        organization_id: Annotated[int, Header(alias="X-Organization-ID")],
    ) -> AttachmentRead:
        return service.get_attachment(organization_id, attachment_id)

    return router
