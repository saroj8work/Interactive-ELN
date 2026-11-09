from typing import Annotated, Any, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import TypeAdapter
import httpx

from eln_common.contracts import MicroplateRead
from .auth import Principal, get_principal
from .client import ServiceClient

MICROPLATE = TypeAdapter(MicroplateRead)
MICROPLATE_LIST = TypeAdapter(list[MicroplateRead])
ANY_DICT = TypeAdapter(dict[str, Any])


def get_service_client(request: Request) -> ServiceClient:
    return request.app.state.service_client


ServiceClientDep = Annotated[ServiceClient, Depends(get_service_client)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]

plates_router = APIRouter(prefix="/api/plates", tags=["plates"])


@plates_router.post("", status_code=status.HTTP_201_CREATED)
async def create_plate(
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> MicroplateRead:
    return await client.post(
        "plates",
        "/plates",
        payload,
        MICROPLATE,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@plates_router.get("")
async def list_plates(
    client: ServiceClientDep,
    principal: PrincipalDep,
    project_id: Optional[int] = Query(None),
    experiment_id: Optional[int] = Query(None),
) -> list[MicroplateRead]:
    path = "/plates"
    params = []
    if project_id is not None:
        params.append(f"project_id={project_id}")
    if experiment_id is not None:
        params.append(f"experiment_id={experiment_id}")
    if params:
        path += "?" + "&".join(params)

    return await client.get(
        "plates",
        path,
        MICROPLATE_LIST,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@plates_router.get("/{plate_id}")
async def get_plate(
    plate_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> MicroplateRead:
    return await client.get(
        "plates",
        f"/plates/{plate_id}",
        MICROPLATE,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@plates_router.put("/{plate_id}/wells")
async def update_wells(
    plate_id: int,
    payload: dict[str, Any],
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> MicroplateRead:
    return await client.put(
        "plates",
        f"/plates/{plate_id}/wells",
        payload,
        MICROPLATE,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@plates_router.post("/{plate_id}/calculate")
async def calculate_plate(
    plate_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.post(
        "plates",
        f"/plates/{plate_id}/calculate",
        {},
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@plates_router.get("/{plate_id}/heatmap")
async def get_heatmap(
    plate_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
) -> dict[str, Any]:
    return await client.get(
        "plates",
        f"/plates/{plate_id}/heatmap",
        ANY_DICT,
        organization_id=principal.organization_id,
        user_id=principal.user_id,
        organization_role=principal.role,
    )


@plates_router.post("/{plate_id}/readings/csv")
async def upload_csv_readings(
    plate_id: int,
    client: ServiceClientDep,
    principal: PrincipalDep,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    content = (await file.read()).decode("utf-8", errors="ignore")
    plates_url = client._settings.url_for("plates")
    async with httpx.AsyncClient(timeout=15.0) as http:
        files = {"file": ("readings.csv", content.encode("utf-8"), "text/csv")}
        headers = {
            "X-Organization-ID": str(principal.organization_id),
            "X-User-ID": str(principal.user_id),
            "X-Organization-Role": principal.role,
        }
        res = await http.post(f"{plates_url}/plates/{plate_id}/readings/csv", files=files, headers=headers)
        if res.is_error:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()

