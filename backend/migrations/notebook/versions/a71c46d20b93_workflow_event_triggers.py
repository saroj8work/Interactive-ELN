"""Add project workflow triggers for experiment and entry creation.

Revision ID: a71c46d20b93
Revises: f45c0b724a1e
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a71c46d20b93"
down_revision: Union[str, None] = "f45c0b724a1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflow_rules",
        sa.Column(
            "trigger_type",
            sa.String(length=40),
            server_default="experiment_status_changed",
            nullable=False,
        ),
    )
    op.alter_column(
        "workflow_rules",
        "to_status",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    op.alter_column("workflow_rules", "trigger_type", server_default=None)


def downgrade() -> None:
    op.execute("UPDATE workflow_rules SET to_status = 'completed' WHERE to_status IS NULL")
    op.alter_column(
        "workflow_rules",
        "to_status",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.drop_column("workflow_rules", "trigger_type")
