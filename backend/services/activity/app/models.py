from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from eln_common.database import Base


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    source_service: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(48), index=True)
    entity_type: Mapped[str] = mapped_column(String(48), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    organization_id: Mapped[int] = mapped_column(Integer, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    details: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
