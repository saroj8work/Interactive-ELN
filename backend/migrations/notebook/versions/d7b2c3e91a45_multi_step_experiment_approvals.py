"""Add ordered reviewer steps to experiment approvals.

Revision ID: d7b2c3e91a45
Revises: c2f19a6d7e40
"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7b2c3e91a45"
down_revision: Union[str, None] = "c2f19a6d7e40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experiment_approvals",
        sa.Column("reviewer_user_ids", sa.JSON(), nullable=True),
    )
    op.add_column(
        "experiment_approvals",
        sa.Column("current_step_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "experiment_approvals",
        sa.Column("step_history", sa.JSON(), nullable=True),
    )
    table = sa.table(
        "experiment_approvals",
        sa.column("id", sa.Integer()),
        sa.column("reviewer_user_id", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("decision_comment", sa.Text()),
        sa.column("decided_by_user_id", sa.Integer()),
        sa.column("decided_at", sa.DateTime(timezone=True)),
        sa.column("reviewer_user_ids", sa.JSON()),
        sa.column("step_history", sa.JSON()),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(
            table.c.id,
            table.c.reviewer_user_id,
            table.c.status,
            table.c.decision_comment,
            table.c.decided_by_user_id,
            table.c.decided_at,
        )
    )
    for row in rows:
        history = [{
            "step_order": 1,
            "reviewer_user_id": row.reviewer_user_id,
            "status": row.status,
            "comment": row.decision_comment or "",
            "decided_by_user_id": row.decided_by_user_id,
            "decided_at": row.decided_at.isoformat() if isinstance(row.decided_at, datetime) else None,
        }]
        connection.execute(
            table.update()
            .where(table.c.id == row.id)
            .values(reviewer_user_ids=[row.reviewer_user_id], step_history=history)
        )
    op.alter_column("experiment_approvals", "reviewer_user_ids", nullable=False)
    op.alter_column("experiment_approvals", "step_history", nullable=False)
    op.alter_column("experiment_approvals", "current_step_index", server_default=None)


def downgrade() -> None:
    op.drop_column("experiment_approvals", "step_history")
    op.drop_column("experiment_approvals", "current_step_index")
    op.drop_column("experiment_approvals", "reviewer_user_ids")
