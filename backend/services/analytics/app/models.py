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


class ScientificSpreadsheet(Base):
    __tablename__ = "scientific_spreadsheets"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, nullable=True, index=True)
    experiment_id = Column(Integer, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False, default="")
    sheet_data_json = Column(Text, nullable=False, default="{}")
    curves_data_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_sheet_org_exp", "organization_id", "experiment_id"),
    )

