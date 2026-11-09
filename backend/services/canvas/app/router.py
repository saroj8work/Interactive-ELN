import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from eln_common.database import Database
from .service import CanvasService, PRESET_TEMPLATES


class CreateCanvasRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    project_id: Optional[int] = None
    experiment_id: Optional[int] = None


class UpdateCanvasRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None


class ValidateDagRequest(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class StepRunRequest(BaseModel):
    completed_node_id: str


def create_router(database: Database) -> APIRouter:
    router = APIRouter()

    @router.get("/canvas/templates")
    def get_templates() -> list[dict[str, Any]]:
        return PRESET_TEMPLATES

    @router.post("/canvas/validate")
    def validate_dag(payload: ValidateDagRequest) -> dict[str, Any]:
        with database.session_factory() as session:
            service = CanvasService(session)
            return service.validate_dag(payload.nodes, payload.edges)

    @router.post("/canvas", status_code=status.HTTP_201_CREATED)
    def create_canvas(
        payload: CreateCanvasRequest,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = CanvasService(session)
            c = service.create_canvas(
                organization_id=organization_id,
                name=payload.name,
                description=payload.description,
                nodes=payload.nodes,
                edges=payload.edges,
                project_id=payload.project_id,
                experiment_id=payload.experiment_id,
            )
            return {
                "id": c.id,
                "organization_id": c.organization_id,
                "project_id": c.project_id,
                "experiment_id": c.experiment_id,
                "name": c.name,
                "description": c.description,
                "status": c.status,
                "nodes": json.loads(c.nodes_json),
                "edges": json.loads(c.edges_json),
                "created_at": c.created_at.isoformat(),
            }

    @router.get("/canvas")
    def list_canvases(
        organization_id: int = Query(..., alias="organization_id"),
        project_id: Optional[int] = Query(None),
        experiment_id: Optional[int] = Query(None),
    ) -> list[dict[str, Any]]:
        with database.session_factory() as session:
            service = CanvasService(session)
            items = service.list_canvases(organization_id, project_id, experiment_id)
            return [
                {
                    "id": c.id,
                    "organization_id": c.organization_id,
                    "project_id": c.project_id,
                    "experiment_id": c.experiment_id,
                    "name": c.name,
                    "description": c.description,
                    "status": c.status,
                    "nodes": json.loads(c.nodes_json),
                    "edges": json.loads(c.edges_json),
                    "created_at": c.created_at.isoformat(),
                }
                for c in items
            ]

    @router.get("/canvas/{canvas_id}")
    def get_canvas(
        canvas_id: int,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = CanvasService(session)
            c = service.get_canvas(canvas_id, organization_id)
            if not c:
                raise HTTPException(status_code=404, detail="Workflow canvas not found")
            return {
                "id": c.id,
                "organization_id": c.organization_id,
                "project_id": c.project_id,
                "experiment_id": c.experiment_id,
                "name": c.name,
                "description": c.description,
                "status": c.status,
                "nodes": json.loads(c.nodes_json),
                "edges": json.loads(c.edges_json),
                "created_at": c.created_at.isoformat(),
            }

    @router.put("/canvas/{canvas_id}")
    def update_canvas(
        canvas_id: int,
        payload: UpdateCanvasRequest,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = CanvasService(session)
            c = service.update_canvas(
                canvas_id=canvas_id,
                organization_id=organization_id,
                name=payload.name,
                nodes=payload.nodes,
                edges=payload.edges,
                status=payload.status,
            )
            if not c:
                raise HTTPException(status_code=404, detail="Workflow canvas not found")
            return {
                "id": c.id,
                "organization_id": c.organization_id,
                "project_id": c.project_id,
                "experiment_id": c.experiment_id,
                "name": c.name,
                "description": c.description,
                "status": c.status,
                "nodes": json.loads(c.nodes_json),
                "edges": json.loads(c.edges_json),
                "created_at": c.created_at.isoformat(),
            }

    @router.post("/canvas/{canvas_id}/runs", status_code=status.HTTP_201_CREATED)
    def start_execution(
        canvas_id: int,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = CanvasService(session)
            try:
                run = service.start_execution(canvas_id, organization_id)
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=str(ve))
            if not run:
                raise HTTPException(status_code=404, detail="Canvas not found")
            return {
                "id": run.id,
                "canvas_id": run.canvas_id,
                "status": run.status,
                "current_node_id": run.current_node_id,
                "node_states": json.loads(run.node_states_json),
                "logs": json.loads(run.logs_json),
                "started_at": run.started_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }

    @router.post("/canvas/runs/{run_id}/step")
    def step_execution(
        run_id: int,
        payload: StepRunRequest,
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = CanvasService(session)
            run = service.step_execution(run_id, payload.completed_node_id)
            if not run:
                raise HTTPException(status_code=404, detail="Run not found")
            return {
                "id": run.id,
                "canvas_id": run.canvas_id,
                "status": run.status,
                "current_node_id": run.current_node_id,
                "node_states": json.loads(run.node_states_json),
                "logs": json.loads(run.logs_json),
                "started_at": run.started_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }

    @router.get("/canvas/{canvas_id}/runs")
    def list_runs(canvas_id: int) -> list[dict[str, Any]]:
        with database.session_factory() as session:
            service = CanvasService(session)
            runs = service.list_runs(canvas_id)
            return [
                {
                    "id": r.id,
                    "canvas_id": r.canvas_id,
                    "status": r.status,
                    "current_node_id": r.current_node_id,
                    "node_states": json.loads(r.node_states_json),
                    "logs": json.loads(r.logs_json),
                    "started_at": r.started_at.isoformat(),
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                }
                for r in runs
            ]

    return router
