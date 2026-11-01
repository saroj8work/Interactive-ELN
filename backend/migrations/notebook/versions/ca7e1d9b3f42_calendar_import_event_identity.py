"""Track iCalendar event identity on equipment bookings.

Revision ID: ca7e1d9b3f42
Revises: 7b3e9c2d5a14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ca7e1d9b3f42"
down_revision: Union[str, None] = "7b3e9c2d5a14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "equipment_bookings",
        sa.Column("source_calendar_uid", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "equipment_bookings",
        sa.Column("source_calendar_recurrence_id", sa.String(length=40), server_default="", nullable=False),
    )
    op.create_index(
        "uq_equipment_booking_calendar_event",
        "equipment_bookings",
        ["organization_id", "equipment_id", "source_calendar_uid", "source_calendar_recurrence_id"],
        unique=True,
        postgresql_where=sa.text("source_calendar_uid IS NOT NULL"),
        sqlite_where=sa.text("source_calendar_uid IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_equipment_booking_calendar_event", table_name="equipment_bookings")
    op.drop_column("equipment_bookings", "source_calendar_recurrence_id")
    op.drop_column("equipment_bookings", "source_calendar_uid")
