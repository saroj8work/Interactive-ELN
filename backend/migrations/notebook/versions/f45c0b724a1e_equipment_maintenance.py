"""Add equipment maintenance scheduling and status tracking.

Revision ID: f45c0b724a1e
Revises: b19e6f4c82ad
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f45c0b724a1e"
down_revision: Union[str, None] = "b19e6f4c82ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "equipment_maintenance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["equipment_id"], ["equipment_resources.id"],
            name="fk_equipment_maintenance_equipment_id_equipment_resources",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_equipment_maintenance"),
    )
    op.create_index("ix_equipment_maintenance_organization_id", "equipment_maintenance", ["organization_id"])
    op.create_index("ix_equipment_maintenance_equipment_id", "equipment_maintenance", ["equipment_id"])
    op.create_index("ix_equipment_maintenance_starts_at", "equipment_maintenance", ["starts_at"])
    op.create_index("ix_equipment_maintenance_ends_at", "equipment_maintenance", ["ends_at"])
    op.create_index("ix_equipment_maintenance_status", "equipment_maintenance", ["status"])


def downgrade() -> None:
    op.drop_index("ix_equipment_maintenance_status", table_name="equipment_maintenance")
    op.drop_index("ix_equipment_maintenance_ends_at", table_name="equipment_maintenance")
    op.drop_index("ix_equipment_maintenance_starts_at", table_name="equipment_maintenance")
    op.drop_index("ix_equipment_maintenance_equipment_id", table_name="equipment_maintenance")
    op.drop_index("ix_equipment_maintenance_organization_id", table_name="equipment_maintenance")
    op.drop_table("equipment_maintenance")
