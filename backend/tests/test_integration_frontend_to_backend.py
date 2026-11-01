"""
Comprehensive Frontend-to-Backend Integration Test Suite
Simulates the exact HTTP requests and workflows initiated by the frontend client (api.ts)
through the API Gateway down to the underlying microservices and database.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import sys

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from eln_common.config import GatewaySettings
from eln_common.database import Base, Database
from eln_common.errors import register_domain_error_handlers
from services.identity.app.security import (
    create_access_token,
    hash_password,
    jwt_secret,
)
from services.identity.app.router import create_router as create_identity_router
from services.projects.app.router import create_router as create_projects_router
from services.notebook.app.router import create_router as create_notebook_router
from services.activity.app.router import create_router as create_activity_router
from gateway.app.client import ServiceClient
from gateway.app.main import app as gateway_app
from seed_data import seed_database


class AsgiRouterTransport(httpx.AsyncBaseTransport):
    """
    In-memory ASGI router transport that directly dispatches HTTP requests
    to FastAPI application instances based on service host/port, without network sockets
    or nested TestClient deadlocks.
    """
    def __init__(self, routes: dict[str, FastAPI]):
        self.transports = {
            key: httpx.ASGITransport(app=app)
            for key, app in routes.items()
        }

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        port = request.url.port
        if "identity" in host or port == 8004:
            return await self.transports["identity"].handle_async_request(request)
        elif "projects" in host or port == 8001:
            return await self.transports["projects"].handle_async_request(request)
        elif "notebook" in host or port == 8002:
            return await self.transports["notebook"].handle_async_request(request)
        elif "activity" in host or port == 8003:
            return await self.transports["activity"].handle_async_request(request)
        raise ValueError(f"Unknown downstream route for {request.url}")


@pytest.fixture(scope="module")
def integration_env():
    """
    Sets up an in-memory SQLite database seeded with full scientific data,
    boots in-process microservice routers, and wires Gateway's ServiceClient
    via an in-memory ASGI transport.
    """
    os.environ["ELN_JWT_SECRET"] = "super-secret-key-that-is-at-least-32-bytes-long!"
    os.environ["ELN_AUDIT_HMAC_KEY"] = "super-secret-hmac-key-at-least-32-bytes-long!"
    from cryptography.fernet import Fernet
    os.environ["ELN_WEBHOOK_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

    db = Database("sqlite://", allow_sqlite_for_tests=True)
    Base.metadata.create_all(bind=db.engine)

    with db.session() as session:
        seed_counts = seed_database(session)

    # 1. Mount identity app
    identity_app = FastAPI()
    register_domain_error_handlers(identity_app)
    identity_app.include_router(create_identity_router(db))

    # 2. Mount projects app
    projects_app = FastAPI()
    register_domain_error_handlers(projects_app)
    projects_app.include_router(create_projects_router(db))

    # 3. Mount notebook app
    notebook_app = FastAPI()
    register_domain_error_handlers(notebook_app)
    notebook_app.include_router(create_notebook_router(db))

    # 4. Mount activity app
    activity_app = FastAPI()
    register_domain_error_handlers(activity_app)
    activity_app.include_router(create_activity_router(db))

    transport = AsgiRouterTransport({
        "identity": identity_app,
        ":8004": identity_app,
        "projects": projects_app,
        ":8001": projects_app,
        "notebook": notebook_app,
        ":8002": notebook_app,
        "activity": activity_app,
        ":8003": activity_app,
    })
    mock_http_client = httpx.AsyncClient(transport=transport)
    settings = GatewaySettings()

    gateway_app.state.settings = settings
    gateway_app.state.service_client = ServiceClient(settings, client=mock_http_client)
    gateway_app.state.identity_client = mock_http_client

    client = TestClient(gateway_app)
    identity_client = TestClient(identity_app)

    yield {
        "db": db,
        "gateway_client": client,
        "identity_client": identity_client,
        "seed_counts": seed_counts,
    }

    db.engine.dispose()


class TestEndToEndFrontendToBackend:
    """Complete E2E integration test verifying frontend-to-backend workflows."""

    def test_01_auth_flow_login_and_token_generation(self, integration_env):
        """Frontend login screen -> /auth/login -> receives JWT access token."""
        client = integration_env["identity_client"]

        # Valid login as Dr. Elena Rostova (Admin/PI)
        login_resp = client.post(
            "/auth/login",
            json={
                "organization_slug": "biosynth",
                "email": "dr.elena.rostova@biosynth.org",
                "password": "ElenaLab#2026!",
            },
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        data = login_resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

        # Current user profile
        token = data["access_token"]
        me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["email"] == "dr.elena.rostova@biosynth.org"
        assert me_data["role"] == "admin"
        assert me_data["organization_id"] == 1

        # Invalid password rejection
        bad_resp = client.post(
            "/auth/login",
            json={
                "organization_slug": "biosynth",
                "email": "dr.elena.rostova@biosynth.org",
                "password": "WrongPassword123!",
            },
        )
        assert bad_resp.status_code == 401

    def test_02_projects_and_experiment_lifecycle(self, integration_env):
        """Frontend Project & Experiment navigator -> Gateway -> Projects & Notebook services."""
        client = integration_env["gateway_client"]
        token = create_access_token(
            user_id=1,
            organization_id=1,
            role="admin",
            secret=jwt_secret(),
        )
        auth_header = {"Authorization": f"Bearer {token}"}

        # 1. Fetch Projects
        resp = client.get("/api/projects", headers=auth_header)
        assert resp.status_code == 200
        projects = resp.json()
        assert len(projects) >= 3
        assert any(p["name"] == "Kinase Inhibitor Optimization & Synthesis" for p in projects)
        kinase_proj = next(p for p in projects if p["name"] == "Kinase Inhibitor Optimization & Synthesis")

        # 2. Create New Project
        create_resp = client.post(
            "/api/projects",
            headers=auth_header,
            json={"name": "Lipid Nanoparticle Formulation Study", "description": "mRNA delivery vehicle optimization."},
        )
        assert create_resp.status_code == 201
        new_proj = create_resp.json()
        assert new_proj["name"] == "Lipid Nanoparticle Formulation Study"

        # 3. List Experiments in Project
        exp_resp = client.get(f"/api/projects/{kinase_proj['id']}/experiments", headers=auth_header)
        assert exp_resp.status_code == 200
        experiments = exp_resp.json()
        assert len(experiments) >= 2
        suzuki_exp = next(e for e in experiments if "Suzuki-Miyaura" in e["name"])
        assert suzuki_exp["status"] == "completed"

        # 4. Create New Experiment
        new_exp_resp = client.post(
            f"/api/projects/{kinase_proj['id']}/experiments",
            headers=auth_header,
            json={"name": "Solubility & Permeability PAMPA Assay", "description": "High-throughput membrane permeability."},
        )
        assert new_exp_resp.status_code == 201
        new_exp = new_exp_resp.json()
        assert new_exp["status"] == "in_progress"

    def test_03_notebook_entries_and_cross_item_mentions(self, integration_env):
        """Frontend Entry Editor -> Gateway -> Notebook Entry CRUD with LaTeX math and mentions."""
        client = integration_env["gateway_client"]
        token = create_access_token(
            user_id=1,
            organization_id=1,
            role="admin",
            secret=jwt_secret(),
        )
        auth_header = {"Authorization": f"Bearer {token}"}

        # Fetch entries of experiment 1
        resp = client.get("/api/experiments/1/entries", headers=auth_header)
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) >= 2
        entry1 = next(e for e in entries if "Reaction Setup" in e["title"])

        # Verify cross-item mentions and KaTeX formula exist in content
        assert "[@4-Bromobenzaldehyde](#inv:2)" in entry1["content"]
        assert "[@Phenylboronic Acid](#inv:3)" in entry1["content"]
        assert "[#Kinase Inhibitor Lead Compound BS-8042](#smp:3)" in entry1["content"]
        assert "$$k_{obs} = A e^{-\\frac{E_a}{RT}}$$" in entry1["content"]

        # Create new entry with mentions
        create_resp = client.post(
            "/api/experiments/1/entries",
            headers=auth_header,
            json={
                "title": "NMR Structure Confirmation",
                "content": "Referenced reagent [@Sodium Borohydride](#inv:1). Purity verified.",
            },
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["title"] == "NMR Structure Confirmation"

    def test_04_electronic_signatures_and_21_cfr_part_11_challenge(self, integration_env):
        """21 CFR Part 11 signature challenge with password re-auth and cryptographic audit trail."""
        client = integration_env["gateway_client"]
        id_client = integration_env["identity_client"]
        token = create_access_token(
            user_id=1,
            organization_id=1,
            role="admin",
            secret=jwt_secret(),
        )
        auth_header = {"Authorization": f"Bearer {token}"}

        # 1. Verify password challenge endpoint in identity
        verify_resp = id_client.post(
            "/auth/verify-password",
            headers=auth_header,
            json={"password": "ElenaLab#2026!"},
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["valid"] is True

        # Incorrect password
        bad_verify = id_client.post(
            "/auth/verify-password",
            headers=auth_header,
            json={"password": "InvalidPassword123!"},
        )
        assert bad_verify.status_code == 200
        assert bad_verify.json()["valid"] is False

        # 2. Sign Notebook Entry with valid 21 CFR Part 11 password
        sig_resp = client.post(
            "/api/entries/2/signatures",
            headers=auth_header,
            json={
                "entity_type": "entry",
                "entity_id": 2,
                "meaning": "approved",
                "comment": "Final QA sign-off on yield.",
                "password": "ElenaLab#2026!",
            },
        )
        assert sig_resp.status_code == 201
        sig_data = sig_resp.json()
        assert sig_data["meaning"] == "approved"
        assert len(sig_data["record_sha256"]) == 64

        # 3. Export Audit Trail (CSV format)
        csv_resp = client.get("/api/experiments/1/audit-trail/export?format=csv", headers=auth_header)
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]
        assert "Event ID" in csv_resp.text
        assert "Timestamp" in csv_resp.text

        # 4. Export Audit Trail (Cryptographic JSON format)
        json_resp = client.get("/api/experiments/1/audit-trail/export?format=json", headers=auth_header)
        assert json_resp.status_code == 200
        manifest = json_resp.json()
        assert manifest["integrity_verification"]["checked_events"] >= 1
        assert len(manifest["events"]) >= 1

    def test_05_inventory_and_stoichiometry_stock_deduction(self, integration_env):
        """Stoichiometry Table reagent consumption -> Gateway -> Stock adjustment & ledger."""
        client = integration_env["gateway_client"]
        token = create_access_token(
            user_id=1,
            organization_id=1,
            role="admin",
            secret=jwt_secret(),
        )
        auth_header = {"Authorization": f"Bearer {token}"}

        # 1. Fetch Reagents
        resp = client.get("/api/inventory", headers=auth_header)
        assert resp.status_code == 200
        items = resp.json()
        sbh = next(i for i in items if i["name"] == "Sodium Borohydride")
        initial_qty = float(sbh["quantity"])

        # 2. Deduct 0.38 g of reagent (Stoichiometry consumption action)
        deduct_resp = client.post(
            f"/api/inventory/{sbh['id']}/adjustments",
            headers=auth_header,
            json={"quantity_delta": -0.38, "reason": "Consumed in Suzuki-Miyaura reaction run #1"},
        )
        assert deduct_resp.status_code in {200, 201}
        movement = deduct_resp.json()
        assert float(movement["quantity_delta"]) == -0.38
        assert float(movement["resulting_quantity"]) == round(initial_qty - 0.38, 3)

        # 3. Verify stock overdraw prevention
        overdraw_resp = client.post(
            f"/api/inventory/{sbh['id']}/adjustments",
            headers=auth_header,
            json={"quantity_delta": -99999.0, "reason": "Overdraw test"},
        )
        assert overdraw_resp.status_code in {400, 422}

    def test_06_storage_locations_and_2d_plate_sample_grid(self, integration_env):
        """2D Storage Box & Plate Grid -> Gateway -> Locations and Samples."""
        client = integration_env["gateway_client"]
        token = create_access_token(
            user_id=1,
            organization_id=1,
            role="admin",
            secret=jwt_secret(),
        )
        auth_header = {"Authorization": f"Bearer {token}"}

        # 1. Storage Locations Tree
        locs_resp = client.get("/api/storage-locations", headers=auth_header)
        assert locs_resp.status_code == 200
        locations = locs_resp.json()
        assert len(locations) >= 5
        box = next(l for l in locations if l["code"] == "BOX-B01")
        assert box["location_type"] == "box"

        # 2. Sample Records
        samples_resp = client.get("/api/samples", headers=auth_header)
        assert samples_resp.status_code == 200
        samples = samples_resp.json()
        assert len(samples) >= 4
        smp1 = next(s for s in samples if s["external_id"] == "SMP-1001")
        assert smp1["storage_location_id"] == box["id"]
        assert "A1" in smp1["storage_location"]

        # 3. Sample Relocation
        move_resp = client.patch(
            f"/api/samples/{smp1['id']}/location",
            headers=auth_header,
            json={"storage_location_id": box["id"], "storage_location": "Box-B01 (E5)"},
        )
        assert move_resp.status_code == 200
        updated_smp = move_resp.json()
        assert updated_smp["storage_location_id"] == box["id"]
        assert "Cryo Box" in updated_smp["storage_location"]

    def test_07_equipment_recurring_booking_expansion(self, integration_env):
        """Equipment Scheduler -> Gateway -> Recurring reservation batch expansion."""
        client = integration_env["gateway_client"]
        token = create_access_token(
            user_id=1,
            organization_id=1,
            role="admin",
            secret=jwt_secret(),
        )
        auth_header = {"Authorization": f"Bearer {token}"}

        # 1. Fetch Equipment
        resp = client.get("/api/equipment", headers=auth_header)
        assert resp.status_code == 200
        equipments = resp.json()
        uhplc = next(e for e in equipments if "UHPLC" in e["name"])

        # 2. Create Recurring Weekly Booking (4 occurrences)
        now = datetime.now(timezone.utc)
        start_dt = (now + timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(hours=2)

        booking_resp = client.post(
            f"/api/equipment/{uhplc['id']}/bookings/recurring",
            headers=auth_header,
            json={
                "starts_at": start_dt.isoformat(),
                "ends_at": end_dt.isoformat(),
                "purpose": "Routine HPLC Purity QC",
                "recurrence_interval": 1,
                "recurrence_unit": "week",
                "recurrence_count": 4,
            },
        )
        assert booking_resp.status_code == 201
        created_bookings = booking_resp.json()
        assert len(created_bookings) == 4
        assert created_bookings[0]["purpose"] == "Routine HPLC Purity QC"

    def test_08_inbound_instrument_webhook(self, integration_env):
        """Analytical instrument (HPLC/plate reader) -> Inbound webhook -> Notebook Entry update."""
        client = integration_env["gateway_client"]

        # Create webhook endpoint token
        token = create_access_token(
            user_id=1,
            organization_id=1,
            role="admin",
            secret=jwt_secret(),
        )
        wh_resp = client.post(
            "/api/integrations/webhooks",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Agilent UHPLC Autosampler Feed",
                "url": "https://8.8.8.8/webhooks/instruments",
                "event_types": ["experiment.completed", "entry.created"],
            },
        )
        assert wh_resp.status_code == 201
        wh_data = wh_resp.json()
        assert "secret" in wh_data

        # Post instrument readings to inbound webhook
        inbound_resp = client.post(
            "/api/webhooks/inbound/test-token",
            json={
                "experiment_id": 1,
                "entry_id": 1,
                "instrument_name": "Agilent 1290 UHPLC",
                "measurement_type": "HPLC Purity",
                "readings": [
                    {"Retention Time (min)": 3.42, "Peak Area": 1420500, "Purity (%)": 99.4},
                    {"Retention Time (min)": 4.15, "Peak Area": 8500, "Purity (%)": 0.6},
                ],
                "raw_data": "RUN-2026-X99: Injection vol 5 uL, flow rate 0.4 mL/min.",
            },
        )
        assert inbound_resp.status_code == 200
        result = inbound_resp.json()
        assert result["status"] == "success"
