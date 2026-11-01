"""Add sequential approval rejection paths.

Revision ID: 8c2d7f1a6b40
Revises: f3a9c1d6b8e2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c2d7f1a6b40"
down_revision: Union[str, None] = "f3a9c1d6b8e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experiment_approvals",
        sa.Column("rejection_reviewer_user_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "experiment_approvals",
        sa.Column("active_branch", sa.String(length=16), nullable=False, server_default="main"),
    )
    op.alter_column("experiment_approvals", "rejection_reviewer_user_ids", server_default=None)
    op.alter_column("experiment_approvals", "active_branch", server_default=None)
    op.execute(
        "UPDATE experiment_approvals SET step_history = "
        "(SELECT json_agg((value::jsonb || '{\"branch\":\"main\"}'::jsonb)::json) "
        "FROM json_array_elements(step_history) AS items(value)) "
        "WHERE json_typeof(step_history) = 'array' AND json_array_length(step_history) > 0"
    )


def downgrade() -> None:
    op.drop_column("experiment_approvals", "active_branch")
    op.drop_column("experiment_approvals", "rejection_reviewer_user_ids")
