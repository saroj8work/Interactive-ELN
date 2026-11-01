"""Store imported inventory custom fields.

Revision ID: a6c8f912e4b7
Revises: f2a6c9d1843e
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6c8f912e4b7"
down_revision: Union[str, None] = "f2a6c9d1843e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inventory_items",
        sa.Column("custom_fields", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.alter_column("inventory_items", "custom_fields", server_default=None)


def downgrade() -> None:
    op.drop_column("inventory_items", "custom_fields")
