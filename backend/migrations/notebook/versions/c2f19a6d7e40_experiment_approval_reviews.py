"""Add assigned experiment approval reviews.

Revision ID: c2f19a6d7e40
Revises: b7d4e2a19c63
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2f19a6d7e40"
down_revision: Union[str, None] = "b7d4e2a19c63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiment_approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("request_comment", sa.Text(), nullable=False),
        sa.Column("decision_comment", sa.Text(), nullable=False),
        sa.Column("snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("decided_by_user_id", sa.Integer(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "organization_id",
        "experiment_id",
        "requested_by_user_id",
        "reviewer_user_id",
        "status",
    ):
        op.create_index(
            f"ix_experiment_approvals_{column}", "experiment_approvals", [column]
        )
    op.create_index(
        "uq_experiment_approvals_pending",
        "experiment_approvals",
        ["organization_id", "experiment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_experiment_approvals_pending", table_name="experiment_approvals")
    for column in (
        "status",
        "reviewer_user_id",
        "requested_by_user_id",
        "experiment_id",
        "organization_id",
    ):
        op.drop_index(f"ix_experiment_approvals_{column}", table_name="experiment_approvals")
    op.drop_table("experiment_approvals")
