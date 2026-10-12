import asyncio
import io
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest
from sqlalchemy import select

from eln_common.contracts import ActivityEventCreate, ProjectAccessRead, ProjectRead
from eln_common.config import GatewaySettings
from eln_common.database import Base, Database
from eln_common.errors import (
    AuthenticationError,
    EntityNotFoundError,
    InvalidInputError,
    ServiceUnavailableError,
    register_domain_error_handlers,
)
from eln_common.outbox import OutboxEvent, OutboxPublisher
from gateway.app.client import ServiceClient
from pydantic import TypeAdapter
from fastapi import FastAPI
from fastapi.testclient import TestClient
from services.activity.app.models import ActivityEvent
from services.activity.app.repository import ActivityRepository
from services.activity.app.service import ActivityService
from services.notebook.app.models import AuditEvent, Experiment, NotebookEntry
from services.notebook.app.attachment_storage import AttachmentStorage
from services.notebook.app.repository import NotebookRepository
from services.notebook.app.router import create_router as create_notebook_router
from services.notebook.app.service import NotebookService
from services.projects.app.models import Project
from services.projects.app.repository import ProjectRepository
from services.projects.app.router import create_router as create_projects_router
from services.projects.app.service import ProjectService
from services.identity.app.models import PasswordReset
from services.identity.app.repository import IdentityRepository
from services.identity.app.service import IdentityService
from services.identity.app.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)
from gateway.app.router import get_service_client, notebook_router, projects_router


def new_database() -> Database:
    database = Database("sqlite://", allow_sqlite_for_tests=True)
    Base.metadata.create_all(bind=database.engine)
    return database


def test_project_creation_commits_project_and_outbox_event() -> None:
    database = new_database()
    with database.session() as db:
        service = ProjectService(ProjectRepository(db), db)
        project = service.create_project(1, 9, "  Cell study  ", "  Growth conditions  ")

        assert project.name == "Cell study"
        assert project.description == "Growth conditions"
        event = db.scalar(select(OutboxEvent))
        assert event is not None
        assert event.entity_type == "project"
        assert event.entity_id == project.id
    database.engine.dispose()


def test_notebook_flow_and_reliable_outbox() -> None:
    database = new_database()
    with database.session() as db:
        project = Project(organization_id=1, name="Cell study", description="")
        db.add(project)
        db.flush()
        service = NotebookService(NotebookRepository(db), db)

        experiment = service.create_experiment(1, project.id, "Pilot", "")
        entry = service.create_entry(1, experiment.id, "Day 1", "Initial notes")
        updated = service.update_entry(
            1, entry.id, 7, "Day 1 observations", "Revised notes"
        )

        assert updated.content == "Revised notes"
        revisions = service.list_entry_revisions(1, entry.id)
        assert len(revisions) == 1
        assert revisions[0].title == "Day 1"
        assert revisions[0].changed_by_user_id == 7
        restored = service.restore_entry_revision(1, entry.id, revisions[0].id, 8)
        assert restored.title == "Day 1"
        assert restored.content == "Initial notes"
        revisions = service.list_entry_revisions(1, entry.id)
        assert len(revisions) == 2
        assert revisions[0].changed_by_user_id == 8
        assert revisions[0].content == "Revised notes"
        assert len(list(db.scalars(select(OutboxEvent)))) == 4
        assert db.get(Experiment, experiment.id) is not None
        assert db.get(NotebookEntry, entry.id) is not None
    database.engine.dispose()


def test_experiment_status_changes_emit_outbox_events() -> None:
    database = new_database()
    with database.session() as db:
        project = Project(organization_id=41, name="Cell study", description="")
        db.add(project)
        db.flush()
        service = NotebookService(NotebookRepository(db), db)
        experiment = service.create_experiment(41, project.id, "Pilot", "")

        completed = service.update_experiment_status(41, experiment.id, 12, "completed")
        assert completed.status == "completed"
        assert service.update_experiment_status(
            41, experiment.id, 12, "completed"
        ).status == "completed"
        archived = service.update_experiment_status(41, experiment.id, 12, "archived")
        assert archived.status == "archived"
        events = list(db.scalars(select(OutboxEvent)))
        assert [event.action for event in events] == [
            "created",
            "status_changed",
            "status_changed",
        ]
        with pytest.raises(InvalidInputError):
            service.update_experiment_status(41, experiment.id, 12, "deleted")
    database.engine.dispose()


def test_inventory_movements_are_attributed_and_cannot_overdraw_stock() -> None:
    database = new_database()
    values = {
        "name": "PBS",
        "category": "reagent",
        "catalog_number": "PBS-1X",
        "lot_number": "LOT-7",
        "expires_on": None,
        "quantity": Decimal("10.000"),
        "unit": "mL",
        "low_stock_threshold": Decimal("2.000"),
        "location": "Cold room A",
        "notes": "",
    }
    with database.session() as db:
        service = NotebookService(NotebookRepository(db), db)
        item = service.create_inventory_item(41, 12, values)
        service.adjust_stock(41, item.id, 12, Decimal("-3.500"), "Used in assay")
        movements = service.list_stock_movements(41, item.id)
        assert item.quantity == Decimal("6.500")
        assert movements[0].changed_by_user_id == 12
        assert movements[0].resulting_quantity == Decimal("6.500")
        assert movements[1].reason == "Initial stock"
        with pytest.raises(InvalidInputError):
            service.adjust_stock(41, item.id, 15, Decimal("-7"), "Overdraw")
        assert item.quantity == Decimal("6.500")
        assert service.list_inventory(99) == []
    database.engine.dispose()


def test_samples_validate_parent_and_are_organization_scoped() -> None:
    database = new_database()
    with database.session() as db:
        service = NotebookService(NotebookRepository(db), db)
        values = {
            "name": "Cell line vial",
            "sample_type": "cell_line",
            "external_id": "CL-001",
            "project_id": None,
            "parent_sample_id": None,
            "storage_location": "Freezer 2",
            "description": "",
        }
        parent = service.create_sample(41, 12, values)
        child = service.create_sample(
            41, 13, {**values, "name": "Passage 2", "parent_sample_id": parent.id}
        )
        assert child.parent_sample_id == parent.id
        assert [sample.id for sample in service.list_samples(41)] == [child.id, parent.id]
        assert service.list_samples(99) == []
        with pytest.raises(EntityNotFoundError):
            service.create_sample(99, 14, {**values, "parent_sample_id": parent.id})
    database.engine.dispose()


def test_notebook_template_is_organization_scoped_and_applies_sections() -> None:
    database = new_database()
    with database.session() as db:
        project = Project(organization_id=41, name="Cell study", description="")
        db.add(project)
        db.flush()
        experiment = Experiment(
            organization_id=41,
            project_id=project.id,
            name="Pilot",
            description="",
        )
        db.add(experiment)
        db.flush()
        entry = NotebookEntry(
            organization_id=41,
            experiment_id=experiment.id,
            title="Notes",
            content="Existing notes",
        )
        db.add(entry)
        db.commit()
        service = NotebookService(NotebookRepository(db), db)
        template = service.create_template(
            41,
            12,
            {
                "name": "Cell culture record",
                "template_kind": "entry",
                "description": "Daily record",
                "sections": [
                    {"title": "Purpose", "instructions": "", "required": True},
                    {"title": "Observations", "instructions": "", "required": False},
                ],
            },
        )
        updated = service.apply_entry_template(41, entry.id, template.id, 12)
        assert updated.title == "Cell culture record"
        assert "## Purpose" in updated.content
        assert "## Observations" in updated.content
        assert service.list_templates(99) == []
        with pytest.raises(EntityNotFoundError):
            service.update_template(
                41,
                template.id,
                13,
                {
                    "name": "Takeover",
                    "template_kind": "entry",
                    "description": "",
                    "sections": [{"title": "Different"}],
                },
            )
        protocol = service.create_template(
            41,
            12,
            {
                "name": "DNA extraction",
                "template_kind": "protocol",
                "description": "Extraction workflow",
                "sections": [
                    {"title": "Materials", "instructions": "List reagents.", "required": True},
                    {"title": "Procedure", "instructions": "Record steps.", "required": True},
                ],
            },
        )
        new_experiment, protocol_entry = service.create_experiment_from_protocol(
            41, project.id, protocol.id
        )
        assert new_experiment.name == "DNA extraction"
        assert protocol_entry.experiment_id == new_experiment.id
        assert "## Procedure" in protocol_entry.content
        with pytest.raises(InvalidInputError):
            service.create_experiment_from_protocol(41, project.id, template.id)
    database.engine.dispose()


def test_entry_attachments_are_private_named_and_checksummed(tmp_path) -> None:
    database = new_database()
    with database.session() as db:
        experiment = Experiment(
            organization_id=41, project_id=2, name="Pilot", description=""
        )
        db.add(experiment)
        db.flush()
        entry = NotebookEntry(
            organization_id=41,
            experiment_id=experiment.id,
            title="Notes",
            content="",
        )
        db.add(entry)
        db.commit()
        service = NotebookService(
            NotebookRepository(db),
            db,
            AttachmentStorage(str(tmp_path / "attachments")),
        )
        attachment = service.add_attachment(
            41,
            entry.id,
            12,
            "..\\private\\result.csv",
            "text/csv",
            b"sample,value\nA,3\n",
        )
        assert attachment.original_filename == "result.csv"
        assert attachment.uploaded_by_user_id == 12
        assert attachment.size_bytes == len(b"sample,value\nA,3\n")
        assert service.attachment_path(attachment).read_bytes() == b"sample,value\nA,3\n"
        with pytest.raises(EntityNotFoundError):
            service.list_attachments(99, entry.id)
        with pytest.raises(InvalidInputError):
            service.add_attachment(
                41, entry.id, 12, "bad\r\nname.txt", "text/plain", b"x"
            )
    database.engine.dispose()


def test_search_matches_notebook_content_and_respects_organization() -> None:
    database = new_database()
    with database.session() as db:
        project = Project(organization_id=41, name="Cell study", description="")
        db.add(project)
        db.flush()
        experiment = Experiment(
            organization_id=41,
            project_id=project.id,
            name="Pilot",
            description="",
        )
        db.add(experiment)
        db.flush()
        db.add(
            NotebookEntry(
                organization_id=41,
                experiment_id=experiment.id,
                title="Day one",
                content="Measured cytokine output.",
            )
        )
        db.add(
            NotebookEntry(
                organization_id=99,
                experiment_id=experiment.id,
                title="Secret",
                content="cytokine results",
            )
        )
        db.commit()
        service = NotebookService(NotebookRepository(db), db)
        results = service.search(41, "cytokine")
        assert [result["title"] for result in results] == ["Day one"]
        assert results[0]["project_id"] == project.id
        assert service.search(99, "cytokine") == []
        with pytest.raises(InvalidInputError):
            service.search(41, "%")
    database.engine.dispose()


def test_record_tags_are_normalized_scoped_and_searchable() -> None:
    database = new_database()
    with database.session() as db:
        project = Project(organization_id=41, name="Tag study", description="")
        db.add(project)
        db.flush()
        experiment = Experiment(
            organization_id=41,
            project_id=project.id,
            name="Pilot",
            description="",
        )
        db.add(experiment)
        db.flush()
        entry = NotebookEntry(
            organization_id=41,
            experiment_id=experiment.id,
            title="Day one",
            content="Cell assay",
        )
        db.add(entry)
        db.commit()

        service = NotebookService(NotebookRepository(db), db)
        updated = service.replace_record_tags(
            41, "entry", entry.id, 12, [" Cell Culture ", "assay", "cell culture"]
        )
        assert updated["tags"] == ["assay", "cell culture"]
        assert service.get_record_tags(41, "entry", entry.id)["tags"] == [
            "assay",
            "cell culture",
        ]
        assert [hit["title"] for hit in service.search(41, "culture")] == ["Day one"]
        assert service.search(99, "culture") == []
        with pytest.raises(EntityNotFoundError):
            service.get_record_tags(99, "entry", entry.id)
        with pytest.raises(InvalidInputError):
            service.replace_record_tags(41, "entry", entry.id, 12, [" "])
        assert len(list(db.scalars(select(OutboxEvent)))) == 1
    database.engine.dispose()


def test_resource_tags_lifecycle_tasks_and_audit_signature_foundation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ELN_AUDIT_HMAC_KEY", "test-audit-key-with-at-least-32-bytes")
    database = new_database()
    with database.session() as db:
        project = Project(organization_id=41, name="Workflow study", description="")
        db.add(project)
        db.flush()
        service = NotebookService(NotebookRepository(db), db)
        experiment = service.create_experiment(41, project.id, "Pilot", "")
        entry = service.create_entry(41, experiment.id, "Day one", "Initial notes")
        item = service.create_inventory_item(
            41,
            12,
            {
                "name": "Buffer",
                "category": "  cold-chain  ",
                "catalog_number": "",
                "lot_number": "",
                "expires_on": None,
                "quantity": Decimal("3"),
                "unit": "mL",
                "low_stock_threshold": Decimal("1"),
                "location": "Freezer",
                "notes": "",
            },
        )
        sample = service.create_sample(
            41,
            12,
            {
                "name": "Cell line A",
                "sample_type": "cell line",
                "external_id": "CL-A",
                "project_id": project.id,
                "parent_sample_id": None,
                "storage_location": "Freezer 2",
                "description": "",
            },
        )
        service.replace_record_tags(41, "inventory", item.id, 12, ["cold chain"])
        service.replace_record_tags(41, "sample", sample.id, 12, ["cell line"])
        assert service.get_record_tags(41, "inventory", item.id)["tags"] == [
            "cold chain"
        ]
        assert service.get_record_tags(41, "sample", sample.id)["tags"] == [
            "cell line"
        ]
        assert item.category == "cold-chain"

        task = service.create_task(
            41,
            12,
            {
                "project_id": project.id,
                "experiment_id": experiment.id,
                "assigned_to_user_id": None,
                "title": "Review results",
                "description": "",
                "due_at": datetime.now(timezone.utc),
                "priority": "high",
            },
        )
        assert service.update_task_status(41, task.id, 12, "completed").status == "completed"
        assert service.list_tasks(41, project.id)[0].title == "Review results"

        signature = service.create_signature(41, 12, entry.id, "reviewed", "Looks good")
        assert signature.record_sha256
        assert service.verify_audit_chain(41) == {
            "organization_id": 41,
            "valid": True,
            "checked_events": 1,
        }
        audit_event = db.scalar(select(AuditEvent))
        assert audit_event is not None
        audit_event.payload_json = '{"tampered":true}'
        db.commit()
        assert service.verify_audit_chain(41)["valid"] is False
    database.engine.dispose()


def test_archived_resources_are_visible_but_not_usable() -> None:
    database = new_database()
    with database.session() as db:
        service = NotebookService(NotebookRepository(db), db)
        item = service.create_inventory_item(
            41,
            12,
            {
                "name": "Archived reagent",
                "category": "reagent",
                "catalog_number": "",
                "lot_number": "",
                "expires_on": None,
                "quantity": Decimal("1"),
                "unit": "g",
                "low_stock_threshold": Decimal("0"),
                "location": "",
                "notes": "",
            },
        )
        archived = service.update_resource_status(
            41, "inventory", item.id, 12, "archived"
        )
        assert archived.status == "archived"
        assert service.list_inventory(41)[0].status == "archived"
        with pytest.raises(InvalidInputError):
            service.adjust_stock(41, item.id, 12, Decimal("1"), "restock")

        equipment = service.create_equipment(
            41, 12, {"name": "Incubator", "description": "", "location": ""}
        )
        start = datetime.now(timezone.utc) + timedelta(days=1)
        service.create_booking(
            41,
            equipment.id,
            12,
            {
                "starts_at": start,
                "ends_at": start + timedelta(hours=1),
                "purpose": "Cell culture",
                "project_id": None,
            },
        )
        with pytest.raises(InvalidInputError):
            service.update_resource_status(
                41, "equipment", equipment.id, 12, "archived"
            )
    database.engine.dispose()


def test_equipment_bookings_reject_overlap_and_allow_cancelled_slots() -> None:
    database = new_database()
    start = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)
    with database.session() as db:
        service = NotebookService(NotebookRepository(db), db)
        equipment = service.create_equipment(
            41, 12, {"name": "qPCR", "description": "", "location": "Room 2"}
        )
        first = service.create_booking(
            41,
            equipment.id,
            12,
            {
                "starts_at": start,
                "ends_at": datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc),
                "purpose": "Gene expression",
                "project_id": None,
            },
        )
        with pytest.raises(InvalidInputError):
            service.create_booking(
                41,
                equipment.id,
                13,
                {
                    "starts_at": datetime(2026, 10, 10, 9, 30, tzinfo=timezone.utc),
                    "ends_at": datetime(2026, 10, 10, 10, 30, tzinfo=timezone.utc),
                    "purpose": "Overlapping use",
                    "project_id": None,
                },
            )
        service.cancel_booking(41, first.id, 12, False)
        second = service.create_booking(
            41,
            equipment.id,
            13,
            {
                "starts_at": start,
                "ends_at": datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc),
                "purpose": "Reuse released time",
                "project_id": None,
            },
        )
        assert second.status == "reserved"
        adjacent = service.create_booking(
            41,
            equipment.id,
            14,
            {
                "starts_at": datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc),
                "ends_at": datetime(2026, 10, 10, 11, 0, tzinfo=timezone.utc),
                "purpose": "Back-to-back use",
                "project_id": None,
            },
        )
        assert adjacent.status == "reserved"
        with pytest.raises(EntityNotFoundError):
            service.cancel_booking(41, second.id, 12, False)
        service.cancel_booking(41, second.id, 13, False)
        assert service.list_bookings(99) == []
    database.engine.dispose()


def test_equipment_routes_forward_actor_and_admin_headers() -> None:
    database = new_database()
    app = FastAPI()
    register_domain_error_handlers(app)
    app.include_router(create_notebook_router(database))
    client = TestClient(app)
    admin_headers = {
        "X-Organization-ID": "41",
        "X-User-ID": "12",
        "X-Organization-Role": "admin",
    }
    member_headers = {
        "X-Organization-ID": "41",
        "X-User-ID": "13",
        "X-Organization-Role": "member",
    }

    assert client.post(
        "/equipment",
        headers=member_headers,
        json={"name": "qPCR", "description": "", "location": "Room 2"},
    ).status_code == 403
    equipment_response = client.post(
        "/equipment",
        headers=admin_headers,
        json={"name": "qPCR", "description": "", "location": "Room 2"},
    )
    assert equipment_response.status_code == 201
    equipment_id = equipment_response.json()["id"]
    booking_response = client.post(
        f"/equipment/{equipment_id}/bookings",
        headers=member_headers,
        json={
            "starts_at": "2026-10-10T09:00:00Z",
            "ends_at": "2026-10-10T10:00:00Z",
            "purpose": "Gene expression",
            "project_id": None,
        },
    )
    assert booking_response.status_code == 201
    booking_id = booking_response.json()["id"]
    assert datetime.fromisoformat(
        booking_response.json()["starts_at"].replace("Z", "+00:00")
    ).tzinfo is not None
    assert client.post(
        f"/bookings/{booking_id}/cancel",
        headers=admin_headers,
    ).status_code == 200
    database.engine.dispose()


def test_services_reject_invalid_or_missing_records() -> None:
    database = new_database()
    with database.session() as db:
        project_service = ProjectService(ProjectRepository(db), db)
        with pytest.raises(InvalidInputError):
            project_service.create_project(1, 9, "  ", "")

        notebook_service = NotebookService(NotebookRepository(db), db)
        with pytest.raises(EntityNotFoundError):
            notebook_service.create_entry(1, 42, "Orphan", "")
    database.engine.dispose()


def test_activity_ingestion_is_idempotent() -> None:
    database = new_database()
    payload = ActivityEventCreate(
        event_id="event-1",
        source_service="projects",
        action="created",
        entity_type="project",
        entity_id=1,
        organization_id=1,
        occurred_at=datetime.now(timezone.utc),
        details={"name": "Cell study"},
    )
    with database.session() as db:
        service = ActivityService(ActivityRepository(db), db)
        first = service.record_event(payload)
        duplicate = service.record_event(payload)
        assert first.id == duplicate.id
        assert len(list(db.scalars(select(ActivityEvent)))) == 1
    database.engine.dispose()


def test_outbox_publisher_retries_and_marks_delivery() -> None:
    async def verify_delivery() -> None:
        database = new_database()
        with database.session() as db:
            ProjectService(ProjectRepository(db), db).create_project(1, 9, "Project", "")
            event = db.scalar(select(OutboxEvent))
            assert event is not None
            event_id = event.event_id

        attempts = 0

        def respond(_: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(503)
            return httpx.Response(202, json={"accepted": True})

        publisher = OutboxPublisher(database, "http://activity-service")
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await publisher._publish_batch(client)
            with database.session() as db:
                event = db.scalar(
                    select(OutboxEvent).where(OutboxEvent.event_id == event_id)
                )
                assert event is not None
                assert event.published_at is None
                assert event.attempts == 1
            await publisher._publish_batch(client)

        with database.session() as db:
            event = db.scalar(
                select(OutboxEvent).where(OutboxEvent.event_id == event_id)
            )
            assert event is not None
            assert event.published_at is not None
            assert event.attempts == 2
        database.engine.dispose()

    asyncio.run(verify_delivery())


def test_gateway_client_validates_downstream_contract() -> None:
    async def verify_contract() -> None:
        valid_payload = {
            "id": 1,
            "organization_id": 1,
            "name": "Project",
            "description": "",
            "created_at": "2026-10-10T12:00:00Z",
        }
        transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=[valid_payload])
        )
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = ServiceClient(
                GatewaySettings(projects_service_url="http://projects"),
                client=http_client,
            )
            projects = await client.get(
                "projects",
                "/projects",
                TypeAdapter(list[ProjectRead]),
                organization_id=1,
            )
            assert projects[0].id == 1

        invalid_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=[{"unexpected": "shape"}])
        )
        async with httpx.AsyncClient(transport=invalid_transport) as http_client:
            client = ServiceClient(
                GatewaySettings(projects_service_url="http://projects"),
                client=http_client,
            )
            with pytest.raises(ServiceUnavailableError):
                await client.get(
                    "projects",
                    "/projects",
                    TypeAdapter(list[ProjectRead]),
                    organization_id=1,
                )

    asyncio.run(verify_contract())


def test_projects_are_scoped_to_the_authenticated_organization() -> None:
    database = new_database()
    with database.session() as db:
        service = ProjectService(ProjectRepository(db), db)
        project_a = service.create_project(101, 10, "Lab A", "")
        service.create_project(202, 20, "Lab B", "")
        assert [project.name for project in service.list_projects(101, 10, False)] == ["Lab A"]
        assert len(service.list_projects(101, 99, True)) == 1
        with pytest.raises(EntityNotFoundError):
            service.get_project(101, project_a.id, 20, False)
    database.engine.dispose()


def test_project_sharing_roles_and_private_default() -> None:
    database = new_database()
    with database.session() as db:
        service = ProjectService(ProjectRepository(db), db)
        project = service.create_project(101, 10, "Private", "")
        assert service.list_projects(101, 20, False) == []
        with pytest.raises(EntityNotFoundError):
            service.get_project(101, project.id, 20, False)

        service.set_member(101, project.id, 10, False, 20, "viewer")
        assert service.project_access(101, project.id, 20, False) == "viewer"
        assert service.list_projects(101, 20, False) == [project]
        with pytest.raises(EntityNotFoundError):
            service.set_member(101, project.id, 20, False, 30, "editor")
        with pytest.raises(InvalidInputError):
            service.remove_member(101, project.id, 10, False, 10)
        service.set_member(101, project.id, 10, False, 20, "editor")
        assert service.project_access(101, project.id, 20, False) == "editor"
        service.remove_member(101, project.id, 10, False, 20)
        with pytest.raises(EntityNotFoundError):
            service.project_access(101, project.id, 20, False)
        access_events = list(
            db.scalars(
                select(OutboxEvent).where(
                    OutboxEvent.entity_type == "project_access"
                )
            )
        )
        assert [event.action for event in access_events] == [
            "access_granted",
            "access_updated",
            "access_removed",
        ]
    database.engine.dispose()


def test_project_routes_enforce_private_access_and_sharing() -> None:
    database = new_database()
    app = FastAPI()
    register_domain_error_handlers(app)
    app.include_router(create_projects_router(database))
    client = TestClient(app)
    owner_headers = {
        "X-Organization-ID": "101",
        "X-User-ID": "10",
        "X-Organization-Role": "member",
    }
    viewer_headers = {
        "X-Organization-ID": "101",
        "X-User-ID": "20",
        "X-Organization-Role": "member",
    }

    created = client.post(
        "/projects",
        headers=owner_headers,
        json={"name": "Private project", "description": ""},
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert client.get(f"/projects/{project_id}", headers=viewer_headers).status_code == 404

    shared = client.put(
        f"/projects/{project_id}/members/20",
        headers=owner_headers,
        json={"user_id": 20, "role": "viewer"},
    )
    assert shared.status_code == 200
    assert shared.json()["role"] == "viewer"
    assert client.get(f"/projects/{project_id}", headers=viewer_headers).status_code == 200
    database.engine.dispose()


def test_gateway_blocks_viewer_writes_to_notebook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ELN_JWT_SECRET", "test-signing-secret-that-is-at-least-32-bytes")
    class ViewerClient:
        async def get(
            self,
            service: str,
            path: str,
            adapter: TypeAdapter,
            *,
            organization_id: int,
            user_id: int | None = None,
            organization_role: str | None = None,
        ):
            assert (organization_id, user_id, organization_role) == (303, 9, "member")
            assert service == "projects"
            assert path == "/projects/5/access"
            return adapter.validate_python({"project_id": 5, "role": "viewer"})

        async def post(self, *args, **kwargs):
            raise AssertionError("Viewer write reached the Notebook service.")

    app = FastAPI()
    app.include_router(notebook_router)
    app.dependency_overrides[get_service_client] = lambda: ViewerClient()
    client = TestClient(app)
    token = create_access_token(
        user_id=9,
        organization_id=303,
        role="member",
        secret=b"test-signing-secret-that-is-at-least-32-bytes",
    )
    response = client.post(
        "/api/projects/5/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Viewer attempt", "description": ""},
    )
    assert response.status_code == 403


def test_gateway_blocks_viewer_from_changing_entry_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ELN_JWT_SECRET", "test-signing-secret-that-is-at-least-32-bytes")

    class ViewerClient:
        async def get(
            self,
            service: str,
            path: str,
            adapter: TypeAdapter,
            *,
            organization_id: int,
            user_id: int | None = None,
            organization_role: str | None = None,
        ):
            if service == "notebook" and path == "/entries/7":
                return adapter.validate_python(
                    {
                        "id": 7,
                        "experiment_id": 2,
                        "title": "Notes",
                        "content": "",
                        "created_at": "2026-10-10T12:00:00Z",
                        "updated_at": "2026-10-10T12:00:00Z",
                    }
                )
            if service == "notebook" and path == "/experiments/2":
                return adapter.validate_python(
                    {
                        "id": 2,
                        "organization_id": organization_id,
                        "project_id": 5,
                        "name": "Pilot",
                        "description": "",
                        "status": "in_progress",
                        "created_at": "2026-10-10T12:00:00Z",
                        "updated_at": "2026-10-10T12:00:00Z",
                    }
                )
            assert service == "projects"
            assert path == "/projects/5/access"
            return adapter.validate_python({"project_id": 5, "role": "viewer"})

        async def put(self, *args, **kwargs):
            raise AssertionError("Viewer tag update reached the Notebook service.")

    app = FastAPI()
    app.include_router(notebook_router)
    app.dependency_overrides[get_service_client] = lambda: ViewerClient()
    client = TestClient(app)
    token = create_access_token(
        user_id=9,
        organization_id=303,
        role="member",
        secret=b"test-signing-secret-that-is-at-least-32-bytes",
    )
    response = client.put(
        "/api/records/entry/7/tags",
        headers={"Authorization": f"Bearer {token}"},
        json={"entity_type": "entry", "tags": ["confidential"]},
    )
    assert response.status_code == 403


def test_project_export_supports_json_and_csv_with_access_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ELN_JWT_SECRET", "test-signing-secret-that-is-at-least-32-bytes")

    class ExportClient:
        async def get(
            self,
            service: str,
            path: str,
            adapter: TypeAdapter,
            *,
            organization_id: int,
            user_id: int | None = None,
            organization_role: str | None = None,
        ):
            if service == "projects" and path == "/projects/5/access":
                return adapter.validate_python({"project_id": 5, "role": "owner"})
            if service == "projects" and path == "/projects/5":
                return adapter.validate_python(
                    {
                        "id": 5,
                        "organization_id": organization_id,
                        "name": "Cell study",
                        "description": "",
                        "created_at": "2026-10-10T12:00:00Z",
                    }
                )
            if service == "notebook" and path == "/projects/5/experiments":
                return adapter.validate_python(
                    [
                        {
                            "id": 2,
                            "organization_id": organization_id,
                            "project_id": 5,
                            "name": "Pilot",
                            "description": "",
                            "status": "completed",
                            "created_at": "2026-10-10T12:00:00Z",
                            "updated_at": "2026-10-11T12:00:00Z",
                        }
                    ]
                )
            if service == "notebook" and path == "/projects/5/tasks":
                return adapter.validate_python([])
            if service == "notebook" and path == "/projects/5/tags":
                return adapter.validate_python(
                    [
                        {
                            "entity_type": "experiment",
                            "entity_id": 2,
                            "tags": ["pilot"],
                        },
                        {
                            "entity_type": "entry",
                            "entity_id": 7,
                            "tags": ["assay"],
                        },
                    ]
                )
            if service == "notebook" and path == "/entries/7/attachments":
                return adapter.validate_python(
                    [
                        {
                            "id": 50,
                            "organization_id": organization_id,
                            "entry_id": 7,
                            "original_filename": "result.txt",
                            "media_type": "text/plain",
                            "size_bytes": 8,
                            "sha256": "0" * 64,
                            "uploaded_by_user_id": 9,
                            "created_at": "2026-10-10T12:00:00Z",
                        }
                    ]
                )
            assert service == "notebook"
            assert path == "/experiments/2/entries"
            return adapter.validate_python(
                [
                    {
                        "id": 7,
                        "experiment_id": 2,
                        "title": "Day one",
                        "content": 'Measured, then "confirmed".',
                        "created_at": "2026-10-10T12:00:00Z",
                        "updated_at": "2026-10-11T12:00:00Z",
                    }
                ]
            )

        async def get_bytes(
            self, service: str, path: str, *, organization_id: int
        ) -> bytes:
            assert service == "notebook"
            assert path == "/attachments/50/content"
            return b"contents"

    app = FastAPI()
    app.include_router(projects_router)
    app.dependency_overrides[get_service_client] = lambda: ExportClient()
    client = TestClient(app)
    token = create_access_token(
        user_id=9,
        organization_id=303,
        role="member",
        secret=b"test-signing-secret-that-is-at-least-32-bytes",
    )
    headers = {"Authorization": f"Bearer {token}"}

    json_response = client.get("/api/projects/5/export?format=json", headers=headers)
    assert json_response.status_code == 200
    assert json_response.json()["tasks"] == []
    assert json_response.json()["experiments"][0]["entries"][0]["content"] == (
        'Measured, then "confirmed".'
    )
    csv_response = client.get("/api/projects/5/export?format=csv", headers=headers)
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert '"Measured, then ""confirmed""."' in csv_response.text
    zip_response = client.get("/api/projects/5/export?format=zip", headers=headers)
    assert zip_response.status_code == 200
    with ZipFile(io.BytesIO(zip_response.content)) as archive:
        project_export = json.loads(archive.read("project.json"))
        assert project_export["tasks"] == []
        assert project_export["experiments"][0]["tags"] == ["pilot"]
        exported_entry = project_export["experiments"][0]["entries"][0]
        assert exported_entry["tags"] == ["assay"]
        assert exported_entry["attachments"][0]["original_filename"] == "result.txt"
        assert archive.read("attachments/entry-7/50-result.txt") == b"contents"


@pytest.mark.parametrize("with_attachment", [False, True])
def test_project_import_accepts_json_and_safe_attachment_zip(
    monkeypatch: pytest.MonkeyPatch, with_attachment: bool
) -> None:
    monkeypatch.setenv("ELN_JWT_SECRET", "test-signing-secret-that-is-at-least-32-bytes")
    uploaded: list[bytes] = []
    created_tasks: list[dict] = []
    updated_task_statuses: list[str] = []

    class ImportClient:
        async def get(
            self,
            service: str,
            path: str,
            adapter: TypeAdapter,
            *,
            organization_id: int,
            user_id: int | None = None,
            organization_role: str | None = None,
        ):
            if path == "/projects/5/access":
                return adapter.validate_python({"project_id": 5, "role": "owner"})
            if path == "/projects/5":
                return adapter.validate_python(
                    {
                        "id": 5,
                        "organization_id": organization_id,
                        "name": "Destination",
                        "description": "",
                        "created_at": "2026-10-10T12:00:00Z",
                    }
                )
            raise AssertionError(f"Unexpected GET: {service} {path}")

        async def post(
            self,
            service: str,
            path: str,
            payload: dict,
            adapter: TypeAdapter,
            *,
            organization_id: int,
            user_id: int | None = None,
            organization_role: str | None = None,
        ):
            if path == "/projects/5/experiments":
                return adapter.validate_python(
                    {
                        "id": 20,
                        "organization_id": organization_id,
                        "project_id": 5,
                        "name": payload["name"],
                        "description": payload["description"],
                        "status": "in_progress",
                        "created_at": "2026-10-10T12:00:00Z",
                        "updated_at": "2026-10-10T12:00:00Z",
                    }
                )
            if path == "/experiments/20/entries":
                return adapter.validate_python(
                    {
                        "id": 30,
                        "experiment_id": 20,
                        "title": payload["title"],
                        "content": payload["content"],
                        "created_at": "2026-10-10T12:00:00Z",
                        "updated_at": "2026-10-10T12:00:00Z",
                    }
                )
            if path == "/projects/5/tasks":
                created_tasks.append(payload)
                return adapter.validate_python(
                    {
                        **payload,
                        "id": 60,
                        "organization_id": organization_id,
                        "created_by_user_id": user_id,
                        "status": "open",
                        "created_at": "2026-10-10T12:00:00Z",
                        "updated_at": "2026-10-10T12:00:00Z",
                    }
                )
            raise AssertionError(f"Unexpected POST: {service} {path}")

        async def patch(
            self,
            service: str,
            path: str,
            payload: dict,
            adapter: TypeAdapter,
            *,
            organization_id: int,
            user_id: int | None = None,
            organization_role: str | None = None,
        ):
            assert service == "notebook"
            assert path == "/tasks/60/status"
            updated_task_statuses.append(payload["status"])
            return adapter.validate_python(
                {
                    **created_tasks[0],
                    "id": 60,
                    "organization_id": organization_id,
                    "created_by_user_id": user_id,
                    "status": payload["status"],
                    "created_at": "2026-10-10T12:00:00Z",
                    "updated_at": "2026-10-10T12:00:00Z",
                }
            )

        async def post_bytes(
            self,
            service: str,
            path: str,
            content: bytes,
            adapter: TypeAdapter,
            *,
            organization_id: int,
            user_id: int,
            content_type: str,
        ):
            uploaded.append(content)
            return adapter.validate_python(
                {
                    "id": 40,
                    "organization_id": organization_id,
                    "entry_id": 30,
                    "original_filename": "result.txt",
                    "media_type": content_type,
                    "size_bytes": len(content),
                    "sha256": "0" * 64,
                    "uploaded_by_user_id": user_id,
                    "created_at": "2026-10-10T12:00:00Z",
                }
            )

    app = FastAPI()
    app.include_router(projects_router)
    app.dependency_overrides[get_service_client] = lambda: ImportClient()
    client = TestClient(app)
    token = create_access_token(
        user_id=9,
        organization_id=303,
        role="member",
        secret=b"test-signing-secret-that-is-at-least-32-bytes",
    )
    document = {
        "project": {"name": "Source project", "description": ""},
        "experiments": [
            {
                "experiment": {"id": 2, "name": "Pilot", "description": ""},
                "entries": [
                    {
                        "title": "Day one",
                        "content": "Imported notes",
                        "attachments": (
                            [
                                {
                                    "archive_path": "attachments/entry-1/1-result.txt",
                                    "original_filename": "result.txt",
                                    "media_type": "text/plain",
                                }
                            ]
                            if with_attachment
                            else []
                        ),
                    }
                ],
            }
        ],
        "tasks": [
            {
                "experiment_id": 2,
                "title": "Review results",
                "description": "Check the imported measurements.",
                "due_at": "2026-10-12T12:00:00Z",
                "priority": "high",
                "status": "blocked",
            }
        ],
    }
    if with_attachment:
        bundle = io.BytesIO()
        with ZipFile(bundle, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("project.json", json.dumps(document))
            archive.writestr("attachments/entry-1/1-result.txt", b"contents")
        upload = bundle.getvalue()
        filename = "export.zip"
    else:
        upload = json.dumps(document).encode("utf-8")
        filename = "export.json"
    response = client.post(
        "/api/projects/5/import",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (filename, upload, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    assert response.json() == {
        "project_id": 5,
        "experiments_imported": 1,
        "entries_imported": 1,
        "attachments_imported": int(with_attachment),
        "tasks_imported": 1,
    }
    assert created_tasks[0]["experiment_id"] == 20
    assert created_tasks[0]["assigned_to_user_id"] is None
    assert updated_task_statuses == ["blocked"]
    assert uploaded == ([b"contents"] if with_attachment else [])


def test_gateway_requires_access_token_and_uses_token_organization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ELN_JWT_SECRET", "test-signing-secret-that-is-at-least-32-bytes")
    class FakeClient:
        organization_id: int | None = None

        async def get(
            self,
            service: str,
            path: str,
            adapter: TypeAdapter,
            *,
            organization_id: int,
            user_id: int | None = None,
            organization_role: str | None = None,
        ):
            assert service == "projects"
            assert path == "/projects"
            self.organization_id = organization_id
            assert user_id == 9
            assert organization_role == "member"
            return adapter.validate_python(
                [
                    {
                        "id": 1,
                        "organization_id": organization_id,
                        "name": "Private project",
                        "description": "",
                        "created_at": "2026-10-10T12:00:00Z",
                    }
                ]
            )

    fake_client = FakeClient()
    app = FastAPI()
    app.include_router(projects_router)
    app.dependency_overrides[get_service_client] = lambda: fake_client
    client = TestClient(app)

    assert client.get("/api/projects").status_code == 401
    token = create_access_token(
        user_id=9,
        organization_id=303,
        role="member",
        secret=b"test-signing-secret-that-is-at-least-32-bytes",
    )
    response = client.get(
        "/api/projects", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()[0]["organization_id"] == 303
    assert fake_client.organization_id == 303


def test_invite_only_identity_login_refresh_and_revocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RecordingMailer:
        def __init__(self) -> None:
            self.invite_url = ""
            self.reset_url = ""

        def send(self, recipient: str, organization_name: str, invite_url: str) -> None:
            assert recipient == "owner@example.org"
            assert organization_name == "Life Sciences"
            self.invite_url = invite_url

        def send_password_reset(self, recipient: str, reset_url: str) -> None:
            assert recipient == "owner@example.org"
            self.reset_url = reset_url

    monkeypatch.setenv("ELN_JWT_SECRET", "test-signing-secret-that-is-at-least-32-bytes")
    monkeypatch.setenv("PUBLIC_APP_URL", "http://localhost:5173")
    database = new_database()
    mailer = RecordingMailer()

    with database.session() as db:
        service = IdentityService(IdentityRepository(db), db, mailer=mailer)
        organization, invitation_token = service.bootstrap_organization(
            name="Life Sciences",
            slug="life-sciences",
            owner_email="Owner@example.org",
            owner_name="Lab Owner",
        )
        assert organization.slug == "life-sciences"
        assert invitation_token in mailer.invite_url

        user = service.accept_invitation(
            invitation_token, "Lab Owner", "a-secure-password-123"
        )
        assert user.email_verified_at is not None
        assert verify_password("a-secure-password-123", user.password_hash)
        with pytest.raises(InvalidInputError):
            service.accept_invitation(
                invitation_token, "Lab Owner", "a-secure-password-123"
            )

        access_token, refresh_token = service.login(
            "life-sciences", "owner@example.org", "a-secure-password-123"
        )
        principal = decode_access_token(
            access_token, b"test-signing-secret-that-is-at-least-32-bytes"
        )
        assert principal.user_id == user.id
        assert principal.organization_id == organization.id
        assert principal.role == "admin"

        new_access_token, rotated_refresh = service.refresh(refresh_token)
        assert decode_access_token(
            new_access_token, b"test-signing-secret-that-is-at-least-32-bytes"
        ).user_id == user.id
        with pytest.raises(AuthenticationError):
            service.refresh(refresh_token)

        service.logout(rotated_refresh)
        with pytest.raises(AuthenticationError):
            service.refresh(rotated_refresh)

        _, active_refresh = service.login(
            "life-sciences", "owner@example.org", "a-secure-password-123"
        )
        service.request_password_reset("life-sciences", "owner@example.org")
        raw_reset_token = parse_qs(urlsplit(mailer.reset_url).fragment)[
            "password-reset-token"
        ][0]
        reset_record = db.scalar(select(PasswordReset))
        assert reset_record is not None
        assert reset_record.token_hash != raw_reset_token
        service.complete_password_reset(raw_reset_token, "a-new-secure-password-456")
        updated_user = service.get_user(user.id)
        assert updated_user is not None
        assert verify_password("a-new-secure-password-456", updated_user.password_hash)
        with pytest.raises(AuthenticationError):
            service.refresh(active_refresh)
        with pytest.raises(InvalidInputError):
            service.complete_password_reset(
                raw_reset_token, "another-secure-password-789"
            )
        with pytest.raises(AuthenticationError):
            service.login("life-sciences", "owner@example.org", "a-secure-password-123")
    database.engine.dispose()
