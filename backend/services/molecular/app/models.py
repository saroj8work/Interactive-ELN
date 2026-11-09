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


class MolecularSequence(Base):
    __tablename__ = "molecular_sequences"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, nullable=True, index=True)
    experiment_id = Column(Integer, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    sequence_type = Column(String(32), nullable=False, default="dna") # dna, rna, protein
    topology = Column(String(32), nullable=False, default="linear") # linear, circular
    sequence_data = Column(Text, nullable=False)
    length = Column(Integer, nullable=False)
    gc_content = Column(Float, nullable=False)
    melting_temp = Column(Float, nullable=False)
    molecular_weight = Column(Float, nullable=False)
    description = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_mol_org_exp", "organization_id", "experiment_id"),
        Index("ix_mol_name", "name"),
    )

