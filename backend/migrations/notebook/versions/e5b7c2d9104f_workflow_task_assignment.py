"""Add assignee configuration to workflow rules.

Revision ID: e5b7c2d9104f
Revises: d4e8b1c0a632
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5b7c2d9104f"
down_revision: Union[str, None] = "d4e8b1c0a632"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflow_rules", sa.Column("assigned_to_user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_rules", "assigned_to_user_id")
