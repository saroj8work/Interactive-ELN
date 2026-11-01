"""Add approval outcome filters to workflow rules.

Revision ID: f3a9c1d6b8e2
Revises: e8f6c2a1b940
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a9c1d6b8e2"
down_revision: Union[str, None] = "e8f6c2a1b940"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflow_rules",
        sa.Column("approval_outcome", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_rules", "approval_outcome")
