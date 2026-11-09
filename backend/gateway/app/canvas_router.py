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

canvas_router = APIRouter(prefix="/api/canvas", tags=["canvas"])


@canvas_router.get("/templates")
async def get_templates(
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> list[dict[str, Any]]:
    return await client.get(
        "canvas",
        "/canvas/templates",
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@canvas_router.post("/validate")
async def validate_dag(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "canvas",
        "/canvas/validate",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@canvas_router.post("", status_code=status.HTTP_201_CREATED)
async def create_canvas(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "canvas",
        f"/canvas?organization_id={principal.organization_id}",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@canvas_router.get("")
async def list_canvases(
    client: ServiceClientDep,
    principal: PrincipalDep,
    project_id: Optional[int] = Query(None),
    experiment_id: Optional[int] = Query(None),
) -> list[dict[str, Any]]:
    path = f"/canvas?organization_id={principal.organization_id}"
    if project_id is not None:
        path += f"&project_id={project_id}"
    if experiment_id is not None:
        path += f"&experiment_id={experiment_id}"

    return await client.get(
        "canvas",
        path,
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@canvas_router.get("/{canvas_id}")
async def get_canvas(
    canvas_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.get(
        "canvas",
        f"/canvas/{canvas_id}?organization_id={principal.organization_id}",
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@canvas_router.put("/{canvas_id}")
async def update_canvas(
    canvas_id: int,
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.put(
        "canvas",
        f"/canvas/{canvas_id}?organization_id={principal.organization_id}",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@canvas_router.post("/{canvas_id}/runs", status_code=status.HTTP_201_CREATED)
async def start_execution(
    canvas_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "canvas",
        f"/canvas/{canvas_id}/runs?organization_id={principal.organization_id}",
        {},
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@canvas_router.post("/runs/{run_id}/step")
async def step_execution(
    run_id: int,
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "canvas",
        f"/canvas/runs/{run_id}/step",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@canvas_router.get("/{canvas_id}/runs")
async def list_runs(
    canvas_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> list[dict[str, Any]]:
    return await client.get(
        "canvas",
        f"/canvas/{canvas_id}/runs",
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )

