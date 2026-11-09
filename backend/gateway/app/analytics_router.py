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

analytics_router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@analytics_router.post("/fit-4pl")
async def fit_4pl(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "analytics",
        "/analytics/fit-4pl",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@analytics_router.post("/evaluate-formula")
async def evaluate_formula(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "analytics",
        "/analytics/evaluate-formula",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@analytics_router.get("/presets")
async def get_presets(
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> list[dict[str, Any]]:
    return await client.get(
        "analytics",
        "/analytics/presets",
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@analytics_router.post("/sheets", status_code=status.HTTP_201_CREATED)
async def create_sheet(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "analytics",
        f"/analytics/sheets?organization_id={principal.organization_id}",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@analytics_router.get("/sheets")
async def list_sheets(
    client: ServiceClientDep,
    principal: PrincipalDep,
    project_id: Optional[int] = Query(None),
    experiment_id: Optional[int] = Query(None),
) -> list[dict[str, Any]]:
    path = f"/analytics/sheets?organization_id={principal.organization_id}"
    if project_id is not None:
        path += f"&project_id={project_id}"
    if experiment_id is not None:
        path += f"&experiment_id={experiment_id}"

    return await client.get(
        "analytics",
        path,
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@analytics_router.get("/sheets/{sheet_id}")
async def get_sheet(
    sheet_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.get(
        "analytics",
        f"/analytics/sheets/{sheet_id}?organization_id={principal.organization_id}",
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@analytics_router.put("/sheets/{sheet_id}")
async def update_sheet(
    sheet_id: int,
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.put(
        "analytics",
        f"/analytics/sheets/{sheet_id}?organization_id={principal.organization_id}",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )

