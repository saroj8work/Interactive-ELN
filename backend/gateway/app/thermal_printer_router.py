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

thermal_printer_router = APIRouter(prefix="/api/thermal_printer", tags=["thermal_printer"])


@thermal_printer_router.post("/generate-zpl")
async def generate_zpl(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "thermal_printer",
        "/thermal_printer/generate-zpl",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@thermal_printer_router.get("/presets")
async def get_presets(
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> list[dict[str, Any]]:
    return await client.get(
        "thermal_printer",
        "/thermal_printer/presets",
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@thermal_printer_router.get("/protocols-search")
async def search_protocols(
    client: ServiceClientDep,
    principal: PrincipalDep,
    query: Optional[str] = Query(None),
) -> list[dict[str, Any]]:
    path = "/thermal_printer/protocols-search"
    if query:
        path += f"?query={query}"
    return await client.get(
        "thermal_printer",
        path,
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@thermal_printer_router.post("/protocols-import", status_code=status.HTTP_201_CREATED)
async def import_protocol(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "thermal_printer",
        f"/thermal_printer/protocols-import?organization_id={principal.organization_id}",
        payload,
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@thermal_printer_router.get("/imported-protocols")
async def list_imported(
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> list[dict[str, Any]]:
    return await client.get(
        "thermal_printer",
        f"/thermal_printer/imported-protocols?organization_id={principal.organization_id}",
        ANY_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )

