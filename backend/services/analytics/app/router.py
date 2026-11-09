import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from eln_common.database import Database
from .service import AnalyticsService, evaluate_formula


class Fit4plRequest(BaseModel):
    points: List[Dict[str, float]] = Field(min_length=4)


class EvaluateFormulaRequest(BaseModel):
    expression: str
    values: List[float]


class CreateSheetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    sheet_data: Dict[str, Any] = Field(default_factory=dict)
    curves_data: Dict[str, Any] = Field(default_factory=dict)
    project_id: Optional[int] = None
    experiment_id: Optional[int] = None


class UpdateSheetRequest(BaseModel):
    name: Optional[str] = None
    sheet_data: Optional[Dict[str, Any]] = None
    curves_data: Optional[Dict[str, Any]] = None


def create_router(database: Database) -> APIRouter:
    router = APIRouter()

    @router.post("/analytics/fit-4pl")
    def fit_4pl_curve(payload: Fit4plRequest) -> dict[str, Any]:
        with database.session_factory() as session:
            service = AnalyticsService(session)
            try:
                return service.fit_curve(payload.points)
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=str(ve))

    @router.post("/analytics/evaluate-formula")
    def eval_formula(payload: EvaluateFormulaRequest) -> dict[str, float]:
        result = evaluate_formula(payload.expression, payload.values)
        return {"result": round(float(result), 4)}

    @router.get("/analytics/presets")
    def get_presets() -> list[dict[str, Any]]:
        with database.session_factory() as session:
            service = AnalyticsService(session)
            return service.get_presets()

    @router.post("/analytics/sheets", status_code=status.HTTP_201_CREATED)
    def create_sheet(
        payload: CreateSheetRequest,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = AnalyticsService(session)
            sheet = service.create_sheet(
                organization_id=organization_id,
                name=payload.name,
                description=payload.description,
                sheet_data=payload.sheet_data,
                curves_data=payload.curves_data,
                project_id=payload.project_id,
                experiment_id=payload.experiment_id,
            )
            return {
                "id": sheet.id,
                "organization_id": sheet.organization_id,
                "project_id": sheet.project_id,
                "experiment_id": sheet.experiment_id,
                "name": sheet.name,
                "description": sheet.description,
                "sheet_data": json.loads(sheet.sheet_data_json),
                "curves_data": json.loads(sheet.curves_data_json),
                "created_at": sheet.created_at.isoformat(),
            }

    @router.get("/analytics/sheets")
    def list_sheets(
        organization_id: int = Query(..., alias="organization_id"),
        project_id: Optional[int] = Query(None),
        experiment_id: Optional[int] = Query(None),
    ) -> list[dict[str, Any]]:
        with database.session_factory() as session:
            service = AnalyticsService(session)
            sheets = service.list_sheets(organization_id, project_id, experiment_id)
            return [
                {
                    "id": s.id,
                    "organization_id": s.organization_id,
                    "project_id": s.project_id,
                    "experiment_id": s.experiment_id,
                    "name": s.name,
                    "description": s.description,
                    "sheet_data": json.loads(s.sheet_data_json),
                    "curves_data": json.loads(s.curves_data_json),
                    "created_at": s.created_at.isoformat(),
                }
                for s in sheets
            ]

    @router.get("/analytics/sheets/{sheet_id}")
    def get_sheet(
        sheet_id: int,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = AnalyticsService(session)
            sheet = service.get_sheet(sheet_id, organization_id)
            if not sheet:
                raise HTTPException(status_code=404, detail="Spreadsheet not found")
            return {
                "id": sheet.id,
                "organization_id": sheet.organization_id,
                "project_id": sheet.project_id,
                "experiment_id": sheet.experiment_id,
                "name": sheet.name,
                "description": sheet.description,
                "sheet_data": json.loads(sheet.sheet_data_json),
                "curves_data": json.loads(sheet.curves_data_json),
                "created_at": sheet.created_at.isoformat(),
            }

    @router.put("/analytics/sheets/{sheet_id}")
    def update_sheet(
        sheet_id: int,
        payload: UpdateSheetRequest,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = AnalyticsService(session)
            sheet = service.update_sheet(
                sheet_id=sheet_id,
                organization_id=organization_id,
                name=payload.name,
                sheet_data=payload.sheet_data,
                curves_data=payload.curves_data,
            )
            if not sheet:
                raise HTTPException(status_code=404, detail="Spreadsheet not found")
            return {
                "id": sheet.id,
                "organization_id": sheet.organization_id,
                "project_id": sheet.project_id,
                "experiment_id": sheet.experiment_id,
                "name": sheet.name,
                "description": sheet.description,
                "sheet_data": json.loads(sheet.sheet_data_json),
                "curves_data": json.loads(sheet.curves_data_json),
                "created_at": sheet.created_at.isoformat(),
            }

    return router

