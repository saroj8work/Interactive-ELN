from typing import Annotated, Any, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import TypeAdapter

from .auth import Principal, get_principal
from .client import ServiceClient

ANY_DICT = TypeAdapter(dict[str, Any])
ANY_LIST = TypeAdapter(list[dict[str, Any]])


def get_service_client(request: Request) -> ServiceClient:
    return request.app.state.service_client


ServiceClientDep = Annotated[ServiceClient, Depends(get_service_client)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]

molecular_router = APIRouter(prefix="/api/molecular", tags=["molecular"])


@molecular_router.post("/analyze")
async def analyze_sequence(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "molecular",
        "/molecular/analyze",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@molecular_router.post("/digest")
async def digest_sequence(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "molecular",
        "/molecular/digest",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@molecular_router.post("/orfs")
async def find_orfs(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> list[dict[str, Any]]:
    return await client.post(
        "molecular",
        "/molecular/orfs",
        payload,
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@molecular_router.post("/primers")
async def test_primers(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "molecular",
        "/molecular/primers",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@molecular_router.get("/enzymes")
async def list_enzymes(
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> list[dict[str, Any]]:
    return await client.get(
        "molecular",
        "/molecular/enzymes",
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@molecular_router.get("/presets")
async def list_presets(
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> list[dict[str, Any]]:
    return await client.get(
        "molecular",
        "/molecular/presets",
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@molecular_router.post("/sequences", status_code=status.HTTP_201_CREATED)
async def save_sequence(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "molecular",
        f"/molecular/sequences?organization_id={principal.organization_id}",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@molecular_router.get("/sequences")
async def list_sequences(
    client: ServiceClientDep,
    principal: PrincipalDep,
    project_id: Optional[int] = Query(None),
    experiment_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
) -> list[dict[str, Any]]:
    path = f"/molecular/sequences?organization_id={principal.organization_id}"
    if project_id is not None:
        path += f"&project_id={project_id}"
    if experiment_id is not None:
        path += f"&experiment_id={experiment_id}"
    if search:
        path += f"&search={search}"

    return await client.get(
        "molecular",
        path,
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@molecular_router.get("/sequences/{sequence_id}")
async def get_sequence(
    sequence_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.get(
        "molecular",
        f"/molecular/sequences/{sequence_id}?organization_id={principal.organization_id}",
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@molecular_router.delete("/sequences/{sequence_id}")
async def delete_sequence(
    sequence_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.delete(
        "molecular",
        f"/molecular/sequences/{sequence_id}?organization_id={principal.organization_id}",
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )

