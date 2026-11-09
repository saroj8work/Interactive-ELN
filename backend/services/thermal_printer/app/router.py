import json
from typing import Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from eln_common.database import Database
from .service import ThermalPrinterService, STANDARD_LABEL_PRESETS


class GenerateZplRequest(BaseModel):
    label_type: str = Field(default="cryovial")
    barcode_data: str = Field(min_length=1, max_length=128)
    sample_name: str = Field(min_length=1, max_length=128)
    lot_number: str = Field(default="LOT-2026-001", max_length=64)
    storage_temp: str = Field(default="-80°C", max_length=32)
    expiry_date: str = Field(default="2027-12-31", max_length=32)
    hazard_symbol: str = Field(default="GHS07", max_length=32)
    dpi: int = Field(default=203)


class ImportProtocolRequest(BaseModel):
    protocol_id_ext: str = Field(min_length=1)


def create_router(database: Database) -> APIRouter:
    router = APIRouter()

    @router.post("/thermal_printer/generate-zpl")
    def generate_zpl(payload: GenerateZplRequest) -> dict[str, Any]:
        with database.session_factory() as session:
            service = ThermalPrinterService(session)
            return service.generate_label(
                label_type=payload.label_type,
                barcode_data=payload.barcode_data,
                sample_name=payload.sample_name,
                lot_number=payload.lot_number,
                storage_temp=payload.storage_temp,
                expiry_date=payload.expiry_date,
                hazard_symbol=payload.hazard_symbol,
                dpi=payload.dpi,
            )

    @router.get("/thermal_printer/presets")
    def get_presets() -> list[dict[str, Any]]:
        return STANDARD_LABEL_PRESETS

    @router.get("/thermal_printer/protocols-search")
    def search_protocols(query: Optional[str] = Query(None)) -> list[dict[str, Any]]:
        with database.session_factory() as session:
            service = ThermalPrinterService(session)
            return service.search_protocols_io(query or "")

    @router.post("/thermal_printer/protocols-import", status_code=status.HTTP_201_CREATED)
    def import_protocol(
        payload: ImportProtocolRequest,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = ThermalPrinterService(session)
            proto = service.import_protocol(organization_id, payload.protocol_id_ext)
            if not proto:
                raise HTTPException(status_code=404, detail="Protocol not found in repository")
            return {
                "id": proto.id,
                "protocol_id_ext": proto.protocol_id_ext,
                "title": proto.title,
                "authors": proto.authors,
                "doi": proto.doi,
                "description": proto.description,
                "steps": json.loads(proto.steps_json),
                "created_at": proto.created_at.isoformat(),
            }

    @router.get("/thermal_printer/imported-protocols")
    def list_imported(
        organization_id: int = Query(..., alias="organization_id"),
    ) -> list[dict[str, Any]]:
        with database.session_factory() as session:
            service = ThermalPrinterService(session)
            items = service.list_imported_protocols(organization_id)
            return [
                {
                    "id": p.id,
                    "protocol_id_ext": p.protocol_id_ext,
                    "title": p.title,
                    "authors": p.authors,
                    "doi": p.doi,
                    "description": p.description,
                    "steps": json.loads(p.steps_json),
                    "created_at": p.created_at.isoformat(),
                }
                for p in items
            ]

    return router

