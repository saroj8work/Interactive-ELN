"""Add organization managed inventory custom field schemas.

Revision ID: b7d4e2a19c63
Revises: a6c8f912e4b7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7d4e2a19c63"
down_revision: Union[str, None] = "a6c8f912e4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_custom_field_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("field_type", sa.String(length=16), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name"),
    )
    op.create_index(
        "ix_inventory_custom_field_definitions_organization_id",
        "inventory_custom_field_definitions",
        ["organization_id"],
    )
    op.create_index(
        "ix_inventory_custom_field_definitions_status",
        "inventory_custom_field_definitions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_custom_field_definitions_status",
        table_name="inventory_custom_field_definitions",
    )
    op.drop_index(
        "ix_inventory_custom_field_definitions_organization_id",
        table_name="inventory_custom_field_definitions",
    )
    op.drop_table("inventory_custom_field_definitions")
