from typing import Annotated, Any, Optional
from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import TypeAdapter

from .auth import Principal, get_principal
from .client import ServiceClient

ANY_DICT = TypeAdapter(dict[str, Any])
ANY_LIST = TypeAdapter(list[dict[str, Any]])


def get_service_client(request: Request) -> ServiceClient:
    return request.app.state.service_client


ServiceClientDep = Annotated[ServiceClient, Depends(get_service_client)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]

dossier_router = APIRouter(prefix="/api/dossier", tags=["dossier"])


@dossier_router.post("/compile", status_code=status.HTTP_201_CREATED)
async def compile_dossier(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "dossier",
        f"/dossier/compile?organization_id={principal.organization_id}",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@dossier_router.get("")
async def list_dossiers(
    client: ServiceClientDep,
    principal: PrincipalDep,
    project_id: Optional[int] = Query(None),
    experiment_id: Optional[int] = Query(None),
) -> list[dict[str, Any]]:
    path = f"/dossier?organization_id={principal.organization_id}"
    if project_id is not None:
        path += f"&project_id={project_id}"
    if experiment_id is not None:
        path += f"&experiment_id={experiment_id}"

    return await client.get(
        "dossier",
        path,
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@dossier_router.get("/{dossier_id}")
async def get_dossier(
    dossier_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.get(
        "dossier",
        f"/dossier/{dossier_id}?organization_id={principal.organization_id}",
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@dossier_router.post("/{dossier_id}/certify")
async def certify_dossier(
    dossier_id: int,
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "dossier",
        f"/dossier/{dossier_id}/certify?organization_id={principal.organization_id}",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )

