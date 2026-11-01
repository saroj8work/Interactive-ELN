"""Add parallel approval mode.

Revision ID: e8f6c2a1b940
Revises: d7b2c3e91a45
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8f6c2a1b940"
down_revision: Union[str, None] = "d7b2c3e91a45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experiment_approvals",
        sa.Column(
            "review_mode",
            sa.String(length=16),
            nullable=False,
            server_default="sequential",
        ),
    )
    op.alter_column("experiment_approvals", "review_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("experiment_approvals", "review_mode")
