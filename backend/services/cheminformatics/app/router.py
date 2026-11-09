from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from eln_common.database import Database
from .service import CheminformaticsService, PRESET_COMPOUNDS


class AnalyzeRequest(BaseModel):
    smiles: str = Field(min_length=1, max_length=1000)
    name: str = Field(default="Molecule", max_length=255)


class SaveCompoundRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    smiles: str = Field(min_length=1, max_length=1000)
    project_id: Optional[int] = None
    experiment_id: Optional[int] = None


def create_router(database: Database) -> APIRouter:
    router = APIRouter()

    def get_service() -> CheminformaticsService:
        db = database.session_factory()
        try:
            return CheminformaticsService(db)
        finally:
            pass # Session closed in handler or cleanup

    @router.post("/cheminformatics/analyze")
    def analyze_smiles(
        payload: AnalyzeRequest,
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = CheminformaticsService(session)
            try:
                return service.analyze_smiles(payload.smiles, payload.name)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"SMILES parsing error: {str(e)}")

    @router.get("/cheminformatics/presets")
    def get_presets() -> list[dict[str, Any]]:
        return PRESET_COMPOUNDS

    @router.post("/cheminformatics/compounds", status_code=status.HTTP_201_CREATED)
    def save_compound(
        payload: SaveCompoundRequest,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = CheminformaticsService(session)
            compound = service.save_compound(
                organization_id=organization_id,
                name=payload.name,
                smiles=payload.smiles,
                project_id=payload.project_id,
                experiment_id=payload.experiment_id,
            )
            return {
                "id": compound.id,
                "organization_id": compound.organization_id,
                "project_id": compound.project_id,
                "experiment_id": compound.experiment_id,
                "name": compound.name,
                "smiles": compound.smiles,
                "formula": compound.formula,
                "molecular_weight": compound.molecular_weight,
                "monoisotopic_mass": compound.monoisotopic_mass,
                "logp": compound.logp,
                "hbd": compound.hbd,
                "hba": compound.hba,
                "rotatable_bonds": compound.rotatable_bonds,
                "tpsa": compound.tpsa,
                "rule_of_five_violations": compound.rule_of_five_violations,
                "drug_likeness_score": compound.drug_likeness_score,
                "ghs_hazard_codes": compound.ghs_hazard_codes,
                "ghs_pictograms": compound.ghs_pictograms,
                "svg_depiction": compound.svg_depiction,
                "created_at": compound.created_at.isoformat(),
            }

    @router.get("/cheminformatics/compounds")
    def list_compounds(
        organization_id: int = Query(..., alias="organization_id"),
        project_id: Optional[int] = Query(None),
        experiment_id: Optional[int] = Query(None),
        search: Optional[str] = Query(None),
    ) -> list[dict[str, Any]]:
        with database.session_factory() as session:
            service = CheminformaticsService(session)
            compounds = service.list_compounds(
                organization_id=organization_id,
                project_id=project_id,
                experiment_id=experiment_id,
                search=search,
            )
            return [
                {
                    "id": c.id,
                    "organization_id": c.organization_id,
                    "project_id": c.project_id,
                    "experiment_id": c.experiment_id,
                    "name": c.name,
                    "smiles": c.smiles,
                    "formula": c.formula,
                    "molecular_weight": c.molecular_weight,
                    "monoisotopic_mass": c.monoisotopic_mass,
                    "logp": c.logp,
                    "hbd": c.hbd,
                    "hba": c.hba,
                    "rotatable_bonds": c.rotatable_bonds,
                    "tpsa": c.tpsa,
                    "rule_of_five_violations": c.rule_of_five_violations,
                    "drug_likeness_score": c.drug_likeness_score,
                    "ghs_hazard_codes": c.ghs_hazard_codes,
                    "ghs_pictograms": c.ghs_pictograms,
                    "svg_depiction": c.svg_depiction,
                    "created_at": c.created_at.isoformat(),
                }
                for c in compounds
            ]

    @router.get("/cheminformatics/compounds/{compound_id}")
    def get_compound(
        compound_id: int,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, Any]:
        with database.session_factory() as session:
            service = CheminformaticsService(session)
            c = service.get_compound(compound_id, organization_id)
            if not c:
                raise HTTPException(status_code=404, detail="Compound not found")
            return {
                "id": c.id,
                "organization_id": c.organization_id,
                "project_id": c.project_id,
                "experiment_id": c.experiment_id,
                "name": c.name,
                "smiles": c.smiles,
                "formula": c.formula,
                "molecular_weight": c.molecular_weight,
                "monoisotopic_mass": c.monoisotopic_mass,
                "logp": c.logp,
                "hbd": c.hbd,
                "hba": c.hba,
                "rotatable_bonds": c.rotatable_bonds,
                "tpsa": c.tpsa,
                "rule_of_five_violations": c.rule_of_five_violations,
                "drug_likeness_score": c.drug_likeness_score,
                "ghs_hazard_codes": c.ghs_hazard_codes,
                "ghs_pictograms": c.ghs_pictograms,
                "svg_depiction": c.svg_depiction,
                "created_at": c.created_at.isoformat(),
            }

    @router.delete("/cheminformatics/compounds/{compound_id}")
    def delete_compound(
        compound_id: int,
        organization_id: int = Query(..., alias="organization_id"),
    ) -> dict[str, bool]:
        with database.session_factory() as session:
            service = CheminformaticsService(session)
            success = service.delete_compound(compound_id, organization_id)
            if not success:
                raise HTTPException(status_code=404, detail="Compound not found")
            return {"deleted": True}

    return router

