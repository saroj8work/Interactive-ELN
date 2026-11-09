import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from eln_common.database import Database
from .service import DossierService


class CompileDossierRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    dossier_type: str = Field(default="GxP Certificate of Analysis", max_length=64)
    summary: str = Field(default="", max_length=5000)
    project_id: Optional[int] = None
    experiment_id: Optional[int] = None
    custom_sections: Optional[List[Dict[str, Any]]] = None


class CertifyDossierRequest(BaseModel):
    user_id: int
    user_name: str


def create_router(database: Database) -> APIRouter:
    router = APIRouter()

    @router.post("/dossier/compile", status_code=status.HTTP_201_CREATED)
    def compile_dossier(
        payload: CompileDossierRequest,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = DossierService(session)
            d = service.compile_dossier(
                organization_id=organization_id,
                title=payload.title,
                dossier_type=payload.dossier_type,
                summary=payload.summary,
                project_id=payload.project_id,
                experiment_id=payload.experiment_id,
                custom_sections=payload.custom_sections,
            )
            return {
                "id": d.id,
                "organization_id": d.organization_id,
                "project_id": d.project_id,
                "experiment_id": d.experiment_id,
                "title": d.title,
                "dossier_type": d.dossier_type,
                "summary": d.summary,
                "sections": json.loads(d.sections_json),
                "sha256_checksum": d.sha256_checksum,
                "status": d.status,
                "created_at": d.created_at.isoformat(),
            }

    @router.get("/dossier")
    def list_dossiers(
        organization_id: int = Query(..., alias="organization_id"),
        project_id: Optional[int] = Query(None),
        experiment_id: Optional[int] = Query(None),
    ) -> list[dict[str, Any]]:
        with database.session_factory() as session:
            service = DossierService(session)
            items = service.list_dossiers(organization_id, project_id, experiment_id)
            return [
                {
                    "id": d.id,
                    "organization_id": d.organization_id,
                    "project_id": d.project_id,
                    "experiment_id": d.experiment_id,
                    "title": d.title,
                    "dossier_type": d.dossier_type,
                    "summary": d.summary,
                    "sections": json.loads(d.sections_json),
                    "sha256_checksum": d.sha256_checksum,
                    "status": d.status,
                    "certified_by_user_name": d.certified_by_user_name,
                    "certified_at": d.certified_at.isoformat() if d.certified_at else None,
                    "created_at": d.created_at.isoformat(),
                }
                for d in items
            ]

    @router.get("/dossier/{dossier_id}")
    def get_dossier(
        dossier_id: int,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = DossierService(session)
            d = service.get_dossier(dossier_id, organization_id)
            if not d:
                raise HTTPException(status_code=404, detail="Dossier not found")
            return {
                "id": d.id,
                "organization_id": d.organization_id,
                "project_id": d.project_id,
                "experiment_id": d.experiment_id,
                "title": d.title,
                "dossier_type": d.dossier_type,
                "summary": d.summary,
                "sections": json.loads(d.sections_json),
                "sha256_checksum": d.sha256_checksum,
                "status": d.status,
                "certified_by_user_name": d.certified_by_user_name,
                "certified_at": d.certified_at.isoformat() if d.certified_at else None,
                "created_at": d.created_at.isoformat(),
            }

    @router.post("/dossier/{dossier_id}/certify")
    def certify_dossier(
        dossier_id: int,
        payload: CertifyDossierRequest,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = DossierService(session)
            d = service.certify_dossier(
                dossier_id=dossier_id,
                organization_id=organization_id,
                user_id=payload.user_id,
                user_name=payload.user_name,
            )
            if not d:
                raise HTTPException(status_code=404, detail="Dossier not found")
            return {
                "id": d.id,
                "status": d.status,
                "certified_by_user_name": d.certified_by_user_name,
                "certified_at": d.certified_at.isoformat() if d.certified_at else None,
                "sha256_checksum": d.sha256_checksum,
            }

    @router.get("/dossier/{dossier_id}/html")
    def render_html(
        dossier_id: int,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> Response:
        with database.session_factory() as session:
            service = DossierService(session)
            html_content = service.render_html_dossier(dossier_id, organization_id)
            if not html_content:
                raise HTTPException(status_code=404, detail="Dossier not found")
            return Response(content=html_content, media_type="text/html")

    return router

