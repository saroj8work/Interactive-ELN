from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from eln_common.database import Base


class Compound(Base):
    __tablename__ = "chemical_compounds"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, nullable=True, index=True)
    experiment_id = Column(Integer, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    smiles = Column(String(1000), nullable=False)
    inchi = Column(String(2000), nullable=True)
    inchi_key = Column(String(64), nullable=True)
    formula = Column(String(128), nullable=False)
    molecular_weight = Column(Float, nullable=False)
    monoisotopic_mass = Column(Float, nullable=False)
    logp = Column(Float, nullable=False)
    hbd = Column(Integer, nullable=False)
    hba = Column(Integer, nullable=False)
    rotatable_bonds = Column(Integer, nullable=False)
    tpsa = Column(Float, nullable=False)
    rule_of_five_violations = Column(Integer, nullable=False)
    drug_likeness_score = Column(Float, nullable=False, default=1.0)
    ghs_hazard_codes = Column(String(255), nullable=False, default="")
    ghs_pictograms = Column(String(255), nullable=False, default="")
    svg_depiction = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_chem_org_exp", "organization_id", "experiment_id"),
        Index("ix_chem_smiles", "smiles"),
    )

