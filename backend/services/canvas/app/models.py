from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from eln_common.database import Base


class WorkflowCanvas(Base):
    __tablename__ = "workflow_canvases"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, nullable=True, index=True)
    experiment_id = Column(Integer, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="draft") # draft, active, archived
    nodes_json = Column(Text, nullable=False, default="[]")
    edges_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_canvas_org_exp", "organization_id", "experiment_id"),
    )


class WorkflowCanvasRun(Base):
    __tablename__ = "workflow_canvas_runs"

    id = Column(Integer, primary_key=True, index=True)
    canvas_id = Column(Integer, ForeignKey("workflow_canvases.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending") # pending, running, completed, failed
    current_node_id = Column(String(64), nullable=True)
    node_states_json = Column(Text, nullable=False, default="{}")
    logs_json = Column(Text, nullable=False, default="[]")
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

