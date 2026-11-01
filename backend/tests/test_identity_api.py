from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from eln_common.database import Base, Database
from services.identity.app.router import create_router
from services.identity.app.models import ApiCredential
from services.identity.app.security import token_digest


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


def test_api_credentials_are_hashed_scoped_and_revocable(
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

    client.post(
        "/auth/bootstrap/organizations",
        headers={"X-Bootstrap-Token": "test-bootstrap-secret-with-over-32-bytes"},
        json={"name": "Lab", "slug": "lab", "owner_email": "owner@example.org", "owner_name": "Owner"},
    )
    invitation = parse_qs(urlsplit(mailer.sent[-1][2]).query)["token"][0]
    client.post("/auth/invitations/accept", json={
        "token": invitation, "display_name": "Owner", "password": "lab-owner-password-123"
    })
    login = client.post("/auth/login", json={
        "organization_slug": "lab", "email": "owner@example.org", "password": "lab-owner-password-123"
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = client.post("/auth/api-credentials", headers=headers, json={
        "name": "Read integration", "scopes": ["read"]
    })
    assert created.status_code == 201
    body = created.json()
    secret = body["secret"]
    assert body["scopes"] == ["read"]
    assert secret.startswith("eln_live_")
    with database.session() as db:
        saved = db.get(ApiCredential, body["id"])
        assert saved is not None
        assert saved.token_hash == token_digest(secret)
        assert saved.token_hash != secret

    authenticated = client.post(
        "/auth/api-credentials/authenticate",
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert authenticated.status_code == 200
    assert authenticated.json()["scopes"] == ["read"]
    rotated = client.post(
        f"/auth/api-credentials/{body['id']}/rotate", headers=headers
    )
    assert rotated.status_code == 200
    rotated_secret = rotated.json()["secret"]
    assert rotated_secret != secret
    assert client.post(
        "/auth/api-credentials/authenticate",
        headers={"Authorization": f"Bearer {secret}"},
    ).status_code == 401
    assert client.post(
        "/auth/api-credentials/authenticate",
        headers={"Authorization": f"Bearer {rotated_secret}"},
    ).status_code == 200
    assert client.delete(f"/auth/api-credentials/{body['id']}", headers=headers).status_code == 204
    assert client.post(
        "/auth/api-credentials/authenticate",
        headers={"Authorization": f"Bearer {rotated_secret}"},
    ).status_code == 401
    assert client.get("/auth/api-credentials", headers=headers).json()[0]["revoked_at"]
    database.engine.dispose()
