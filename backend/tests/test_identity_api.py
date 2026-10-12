from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from eln_common.database import Base, Database
from services.identity.app.router import create_router


class RecordingMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, recipient: str, organization_name: str, invite_url: str) -> None:
        self.sent.append((recipient, organization_name, invite_url))


def test_invite_login_org_admin_refresh_and_logout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ELN_JWT_SECRET", "test-signing-secret-that-is-at-least-32-bytes")
    monkeypatch.setenv("ELN_BOOTSTRAP_TOKEN", "test-bootstrap-secret-with-over-32-bytes")
    monkeypatch.setenv("PUBLIC_APP_URL", "http://localhost:5173")
    database = Database("sqlite://", allow_sqlite_for_tests=True)
    Base.metadata.create_all(bind=database.engine)
    mailer = RecordingMailer()
    app = FastAPI()
    app.include_router(create_router(database, mailer))
    client = TestClient(app, base_url="http://localhost:5173")

    bootstrap = client.post(
        "/auth/bootstrap/organizations",
        headers={"X-Bootstrap-Token": "test-bootstrap-secret-with-over-32-bytes"},
        json={
            "name": "Life Sciences",
            "slug": "life-sciences",
            "owner_email": "owner@example.org",
            "owner_name": "Lab Owner",
        },
    )
    assert bootstrap.status_code == 201
    assert bootstrap.json()["slug"] == "life-sciences"
    query = parse_qs(urlsplit(mailer.sent[-1][2]).query)

    accepted = client.post(
        "/auth/invitations/accept",
        json={
            "token": query["token"][0],
            "display_name": "Lab Owner",
            "password": "lab-owner-password-123",
        },
    )
    assert accepted.status_code == 204

    login = client.post(
        "/auth/login",
        json={
            "organization_slug": "life-sciences",
            "email": "owner@example.org",
            "password": "lab-owner-password-123",
        },
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    assert "eln_refresh" in login.headers["set-cookie"]
    owner_headers = {"Authorization": f"Bearer {access_token}"}
    assert client.get("/auth/me", headers=owner_headers).json()["role"] == "admin"
    assert len(client.get("/auth/admin/users", headers=owner_headers).json()) == 1

    invited = client.post(
        "/auth/admin/invitations",
        headers=owner_headers,
        json={"email": "member@example.org", "role": "member"},
    )
    assert invited.status_code == 202
    member_query = parse_qs(urlsplit(mailer.sent[-1][2]).query)
    member_acceptance = client.post(
        "/auth/invitations/accept",
        json={
            "token": member_query["token"][0],
            "display_name": "Lab Member",
            "password": "lab-member-password-456",
        },
    )
    assert member_acceptance.status_code == 204
    member_login = client.post(
        "/auth/login",
        json={
            "organization_slug": "life-sciences",
            "email": "member@example.org",
            "password": "lab-member-password-456",
        },
    )
    member_headers = {
        "Authorization": f"Bearer {member_login.json()['access_token']}"
    }
    assert client.get("/auth/admin/users", headers=member_headers).status_code == 403

    refreshed = client.post(
        "/auth/refresh", headers={"Origin": "http://localhost:5173"}
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"] != access_token
    assert client.post(
        "/auth/refresh",
        headers={"Origin": "https://attacker.example"},
    ).status_code == 403
    assert client.post(
        "/auth/logout", headers={"Origin": "http://localhost:5173"}
    ).status_code == 204
    database.engine.dispose()
