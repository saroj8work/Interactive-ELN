from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile, File, Form, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from eln_common.database import Database
from .service import PlateService


class WellUpdateSchema(BaseModel):
    coordinate: str
    role: Optional[str] = None
    sample_name: Optional[str] = None
    sample_id: Optional[int] = None
    replicate_group: Optional[str] = None
    standard_concentration: Optional[float] = None
    concentration_unit: Optional[str] = None
    dilution_factor: Optional[float] = None
    raw_value: Optional[float] = None


class BatchWellsUpdateRequest(BaseModel):
    wells: List[WellUpdateSchema]


class CreatePlateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    plate_format: str = Field(default="96-well", description="'96-well', '384-well', or '24-well'")
    project_id: Optional[int] = None
    experiment_id: Optional[int] = None
    description: str = ""
    assay_type: str = "ELISA Absorbance"
    wavelength: str = "450 nm"
    measurement_unit: str = "OD"


class WellResponseSchema(BaseModel):
    id: int
    coordinate: str
    row_letter: str
    col_number: int
    role: str
    sample_name: str
    sample_id: Optional[int]
    replicate_group: str
    standard_concentration: Optional[float]
    concentration_unit: str
    dilution_factor: float
    raw_value: Optional[float]
    corrected_value: Optional[float]
    calculated_concentration: Optional[float]

    class Config:
        from_attributes = True


class MicroplateResponseSchema(BaseModel):
    id: int
    organization_id: int
    project_id: Optional[int]
    experiment_id: Optional[int]
    name: str
    plate_format: str
    rows: int
    cols: int
    description: str
    assay_type: str
    wavelength: str
    measurement_unit: str
    created_at: datetime
    updated_at: datetime
    wells: List[WellResponseSchema]

    class Config:
        from_attributes = True


def create_router(database: Database) -> APIRouter:
    router = APIRouter(tags=["microplates"])

    def get_service(db: Session = Depends(database.dependency)) -> PlateService:
        return PlateService(db)

    @router.post("/plates", response_model=MicroplateResponseSchema, status_code=status.HTTP_201_CREATED)
    def create_plate(
        payload: CreatePlateRequest,
        service: PlateService = Depends(get_service),
        organization_id: int = Header(..., alias="X-Organization-ID"),
        user_id: int = Header(..., alias="X-User-ID"),
        organization_role: str = Header(..., alias="X-Organization-Role"),
    ):
        if organization_role not in ("admin", "editor", "owner"):
            raise HTTPException(status_code=403, detail="Editor or Admin role required to create plates.")
        plate = service.create_plate(
            organization_id=organization_id,
            user_id=user_id,
            name=payload.name,
            plate_format=payload.plate_format,
            project_id=payload.project_id,
            experiment_id=payload.experiment_id,
            description=payload.description,
            assay_type=payload.assay_type,
            wavelength=payload.wavelength,
            measurement_unit=payload.measurement_unit,
        )
        return plate

    @router.get("/plates", response_model=List[MicroplateResponseSchema])
    def list_plates(
        service: PlateService = Depends(get_service),
        organization_id: int = Header(..., alias="X-Organization-ID"),
        project_id: Optional[int] = Query(None),
        experiment_id: Optional[int] = Query(None),
    ):
        return service.list_plates(organization_id=organization_id, project_id=project_id, experiment_id=experiment_id)

    @router.get("/plates/{plate_id}", response_model=MicroplateResponseSchema)
    def get_plate(
        plate_id: int,
        service: PlateService = Depends(get_service),
        organization_id: int = Header(..., alias="X-Organization-ID"),
    ):
        plate = service.get_plate(plate_id, organization_id)
        if not plate:
            raise HTTPException(status_code=404, detail="Microplate not found.")
        return plate

    @router.put("/plates/{plate_id}/wells", response_model=MicroplateResponseSchema)
    def update_wells(
        plate_id: int,
        payload: BatchWellsUpdateRequest,
        service: PlateService = Depends(get_service),
        organization_id: int = Header(..., alias="X-Organization-ID"),
        organization_role: str = Header(..., alias="X-Organization-Role"),
    ):
        if organization_role not in ("admin", "editor", "owner"):
            raise HTTPException(status_code=403, detail="Editor role required to configure wells.")
        try:
            return service.update_wells_batch(plate_id, organization_id, [w.model_dump() for w in payload.wells])
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.post("/plates/{plate_id}/readings/csv")
    async def import_csv_readings(
        plate_id: int,
        file: UploadFile = File(...),
        service: PlateService = Depends(get_service),
        organization_id: int = Header(..., alias="X-Organization-ID"),
        organization_role: str = Header(..., alias="X-Organization-Role"),
    ):
        if organization_role not in ("admin", "editor", "owner"):
            raise HTTPException(status_code=403, detail="Editor role required to import readings.")
        content = (await file.read()).decode("utf-8", errors="ignore")
        updated = service.import_plate_reader_csv(plate_id, organization_id, content)
        return {"plate_id": plate_id, "updated_wells": updated, "status": "success"}

    @router.post("/plates/{plate_id}/calculate")
    def run_quantitation(
        plate_id: int,
        service: PlateService = Depends(get_service),
        organization_id: int = Header(..., alias="X-Organization-ID"),
        organization_role: str = Header(..., alias="X-Organization-Role"),
    ):
        if organization_role not in ("admin", "editor", "owner"):
            raise HTTPException(status_code=403, detail="Editor role required to run assay quantitation.")
        try:
            return service.calculate_quantitation(plate_id, organization_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.get("/plates/{plate_id}/heatmap")
    def get_heatmap(
        plate_id: int,
        service: PlateService = Depends(get_service),
        organization_id: int = Header(..., alias="X-Organization-ID"),
    ):
        try:
            return service.get_heatmap_matrix(plate_id, organization_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return router

