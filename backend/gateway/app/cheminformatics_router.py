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

cheminformatics_router = APIRouter(prefix="/api/cheminformatics", tags=["cheminformatics"])


@cheminformatics_router.post("/analyze")
async def analyze_smiles(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "cheminformatics",
        "/cheminformatics/analyze",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@cheminformatics_router.get("/presets")
async def get_presets(
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> list[dict[str, Any]]:
    return await client.get(
        "cheminformatics",
        "/cheminformatics/presets",
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@cheminformatics_router.post("/compounds", status_code=status.HTTP_201_CREATED)
async def save_compound(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "cheminformatics",
        f"/cheminformatics/compounds?organization_id={principal.organization_id}",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@cheminformatics_router.get("/compounds")
async def list_compounds(
    client: ServiceClientDep,
    principal: PrincipalDep,
    project_id: Optional[int] = Query(None),
    experiment_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
) -> list[dict[str, Any]]:
    path = f"/cheminformatics/compounds?organization_id={principal.organization_id}"
    if project_id is not None:
        path += f"&project_id={project_id}"
    if experiment_id is not None:
        path += f"&experiment_id={experiment_id}"
    if search:
        path += f"&search={search}"

    return await client.get(
        "cheminformatics",
        path,
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@cheminformatics_router.get("/compounds/{compound_id}")
async def get_compound(
    compound_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.get(
        "cheminformatics",
        f"/cheminformatics/compounds/{compound_id}?organization_id={principal.organization_id}",
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@cheminformatics_router.delete("/compounds/{compound_id}")
async def delete_compound(
    compound_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.delete(
        "cheminformatics",
        f"/cheminformatics/compounds/{compound_id}?organization_id={principal.organization_id}",
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )

