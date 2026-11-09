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


class ThermalLabelTemplate(Base):
    __tablename__ = "thermal_label_templates"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    label_type = Column(String(64), nullable=False, default="cryovial") # cryovial, microplate, bottle
    dpi = Column(Integer, nullable=False, default=203) # 203 or 300 dpi
    width_mm = Column(Integer, nullable=False, default=25)
    height_mm = Column(Integer, nullable=False, default=12)
    zpl_template = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class ImportedProtocol(Base):
    __tablename__ = "imported_protocols"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    protocol_id_ext = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    authors = Column(String(255), nullable=False, default="")
    doi = Column(String(128), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    steps_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_proto_org_ext", "organization_id", "protocol_id_ext"),
    )

