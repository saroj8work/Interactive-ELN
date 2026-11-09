from typing import Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from eln_common.database import Database
from .service import MolecularService, PRESET_SEQUENCES, RESTRICTION_ENZYMES


class AnalyzeSeqRequest(BaseModel):
    sequence: str = Field(min_length=1)
    name: str = Field(default="Sequence", max_length=255)
    sequence_type: str = Field(default="dna", max_length=32)


class DigestRequest(BaseModel):
    sequence: str = Field(min_length=1)
    enzymes: List[str] = Field(default_factory=list)
    topology: str = Field(default="linear")


class OrfRequest(BaseModel):
    sequence: str = Field(min_length=1)
    min_aa: int = Field(default=30, ge=10, le=5000)


class PrimerPairRequest(BaseModel):
    forward: str = Field(min_length=10, max_length=60)
    reverse: str = Field(min_length=10, max_length=60)


class SaveSequenceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sequence: str = Field(min_length=1)
    sequence_type: str = Field(default="dna", max_length=32)
    topology: str = Field(default="linear", max_length=32)
    project_id: Optional[int] = None
    experiment_id: Optional[int] = None
    description: str = Field(default="", max_length=2000)


def create_router(database: Database) -> APIRouter:
    router = APIRouter()

    @router.post("/molecular/analyze")
    def analyze_sequence(payload: AnalyzeSeqRequest) -> dict[str, Any]:
        with database.session_factory() as session:
            service = MolecularService(session)
            return service.analyze_sequence(payload.sequence, payload.name, payload.sequence_type)

    @router.post("/molecular/digest")
    def digest_sequence(payload: DigestRequest) -> dict[str, Any]:
        with database.session_factory() as session:
            service = MolecularService(session)
            return service.digest(payload.sequence, payload.enzymes, payload.topology)

    @router.post("/molecular/orfs")
    def find_orfs(payload: OrfRequest) -> list[dict[str, Any]]:
        with database.session_factory() as session:
            service = MolecularService(session)
            return service.find_orfs(payload.sequence, payload.min_aa)

    @router.post("/molecular/primers")
    def test_primers(payload: PrimerPairRequest) -> dict[str, Any]:
        with database.session_factory() as session:
            service = MolecularService(session)
            return service.test_primers(payload.forward, payload.reverse)

    @router.get("/molecular/enzymes")
    def list_enzymes() -> list[dict[str, Any]]:
        return RESTRICTION_ENZYMES

    @router.get("/molecular/presets")
    def list_presets() -> list[dict[str, Any]]:
        return PRESET_SEQUENCES

    @router.post("/molecular/sequences", status_code=status.HTTP_201_CREATED)
    def save_sequence(
        payload: SaveSequenceRequest,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = MolecularService(session)
            rec = service.save_sequence(
                organization_id=organization_id,
                name=payload.name,
                sequence_data=payload.sequence,
                sequence_type=payload.sequence_type,
                topology=payload.topology,
                project_id=payload.project_id,
                experiment_id=payload.experiment_id,
                description=payload.description,
            )
            return {
                "id": rec.id,
                "organization_id": rec.organization_id,
                "project_id": rec.project_id,
                "experiment_id": rec.experiment_id,
                "name": rec.name,
                "sequence_type": rec.sequence_type,
                "topology": rec.topology,
                "length": rec.length,
                "gc_content": rec.gc_content,
                "melting_temp": rec.melting_temp,
                "molecular_weight": rec.molecular_weight,
                "description": rec.description,
                "created_at": rec.created_at.isoformat(),
            }

    @router.get("/molecular/sequences")
    def list_sequences(
        organization_id: int = Query(..., alias="organization_id"),
        project_id: Optional[int] = Query(None),
        experiment_id: Optional[int] = Query(None),
        search: Optional[str] = Query(None),
    ) -> list[dict[str, Any]]:
        with database.session_factory() as session:
            service = MolecularService(session)
            seqs = service.list_sequences(
                organization_id=organization_id,
                project_id=project_id,
                experiment_id=experiment_id,
                search=search,
            )
            return [
                {
                    "id": s.id,
                    "organization_id": s.organization_id,
                    "project_id": s.project_id,
                    "experiment_id": s.experiment_id,
                    "name": s.name,
                    "sequence_type": s.sequence_type,
                    "topology": s.topology,
                    "length": s.length,
                    "gc_content": s.gc_content,
                    "melting_temp": s.melting_temp,
                    "molecular_weight": s.molecular_weight,
                    "description": s.description,
                    "created_at": s.created_at.isoformat(),
                }
                for s in seqs
            ]

    @router.get("/molecular/sequences/{sequence_id}")
    def get_sequence(
        sequence_id: int,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = MolecularService(session)
            s = service.get_sequence(sequence_id, organization_id)
            if not s:
                raise HTTPException(status_code=404, detail="Sequence not found")
            return {
                "id": s.id,
                "organization_id": s.organization_id,
                "project_id": s.project_id,
                "experiment_id": s.experiment_id,
                "name": s.name,
                "sequence_data": s.sequence_data,
                "sequence_type": s.sequence_type,
                "topology": s.topology,
                "length": s.length,
                "gc_content": s.gc_content,
                "melting_temp": s.melting_temp,
                "molecular_weight": s.molecular_weight,
                "description": s.description,
                "created_at": s.created_at.isoformat(),
            }

    @router.delete("/molecular/sequences/{sequence_id}")
    def delete_sequence(
        sequence_id: int,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, bool]:
        with database.session_factory() as session:
            service = MolecularService(session)
            ok = service.delete_sequence(sequence_id, organization_id)
            if not ok:
                raise HTTPException(status_code=404, detail="Sequence not found")
            return {"deleted": True}

    return router

