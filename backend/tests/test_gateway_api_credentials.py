from types import SimpleNamespace

import httpx
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from gateway.app.auth import get_principal


def test_api_credential_scope_is_enforced_at_gateway() -> None:
    async def identity_response(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/api-credentials/authenticate"
        assert request.headers["Authorization"] == "Bearer eln_live_test-secret"
        return httpx.Response(
            200,
            json={
                "user_id": 7,
                "organization_id": 9,
                "role": "member",
                "scopes": ["read"],
            },
        )

    app = FastAPI()
    app.state.settings = SimpleNamespace(identity_service_url="http://identity")
    app.state.identity_client = httpx.AsyncClient(transport=httpx.MockTransport(identity_response))

    @app.get("/records")
    async def read_records(principal=Depends(get_principal)):
        return {"organization_id": principal.organization_id}

    @app.post("/records")
    async def write_records(principal=Depends(get_principal)):
        return {"organization_id": principal.organization_id}

    client = TestClient(app)
    headers = {"Authorization": "Bearer eln_live_test-secret"}
    assert client.get("/records", headers=headers).json() == {"organization_id": 9}
    assert client.post("/records", headers=headers).status_code == 403
