"""Add service provider and recurring maintenance settings.

Revision ID: c31ad9e5b204
Revises: a71c46d20b93
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c31ad9e5b204"
down_revision: Union[str, None] = "a71c46d20b93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "equipment_maintenance",
        sa.Column("service_provider", sa.String(length=200), nullable=False, server_default=""),
    )
    op.add_column(
        "equipment_maintenance",
        sa.Column("recurrence_days", sa.Integer(), nullable=True),
    )
    op.alter_column("equipment_maintenance", "service_provider", server_default=None)


def downgrade() -> None:
    op.drop_column("equipment_maintenance", "recurrence_days")
    op.drop_column("equipment_maintenance", "service_provider")
