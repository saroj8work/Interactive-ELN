"""Add week and month equipment maintenance recurrence.

Revision ID: f2a6c9d1843e
Revises: e5b7c2d9104f
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a6c9d1843e"
down_revision: Union[str, None] = "e5b7c2d9104f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("equipment_maintenance", sa.Column("recurrence_unit", sa.String(length=8), nullable=True))
    op.add_column("equipment_maintenance", sa.Column("recurrence_anchor_day", sa.Integer(), nullable=True))
    op.execute("UPDATE equipment_maintenance SET recurrence_unit = 'days' WHERE recurrence_days IS NOT NULL")


def downgrade() -> None:
    op.drop_column("equipment_maintenance", "recurrence_anchor_day")
    op.drop_column("equipment_maintenance", "recurrence_unit")
