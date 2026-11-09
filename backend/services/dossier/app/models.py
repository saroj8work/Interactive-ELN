from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from eln_common.database import Base


class RegulatoryDossier(Base):
    __tablename__ = "regulatory_dossiers"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, nullable=True, index=True)
    experiment_id = Column(Integer, nullable=True, index=True)
    title = Column(String(255), nullable=False)
    dossier_type = Column(String(64), nullable=False, default="GxP Certificate of Analysis")
    summary = Column(Text, nullable=False, default="")
    sections_json = Column(Text, nullable=False, default="[]")
    sha256_checksum = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="draft") # draft, certified, submitted, archived
    certified_by_user_id = Column(Integer, nullable=True)
    certified_by_user_name = Column(String(128), nullable=True)
    certified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_dossier_org_exp", "organization_id", "experiment_id"),
    )

