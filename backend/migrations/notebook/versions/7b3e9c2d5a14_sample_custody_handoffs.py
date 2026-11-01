"""Track sample custody and recipient-confirmed handoffs.

Revision ID: 7b3e9c2d5a14
Revises: 8c2d7f1a6b40
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b3e9c2d5a14"
down_revision: Union[str, None] = "8c2d7f1a6b40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("samples", sa.Column("current_custodian_user_id", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE samples SET current_custodian_user_id = created_by_user_id "
        "WHERE current_custodian_user_id IS NULL"
    )
    op.alter_column("samples", "current_custodian_user_id", nullable=False)
    op.create_index(
        "ix_samples_current_custodian_user_id",
        "samples",
        ["current_custodian_user_id"],
    )
    op.create_table(
        "sample_custody_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("sample_id", sa.Integer(), sa.ForeignKey("samples.id"), nullable=False),
        sa.Column("from_user_id", sa.Integer(), nullable=False),
        sa.Column("to_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("request_note", sa.Text(), nullable=False),
        sa.Column("receipt_note", sa.Text(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in ("organization_id", "sample_id", "from_user_id", "to_user_id", "status"):
        op.create_index(f"ix_sample_custody_transfers_{column}", "sample_custody_transfers", [column])
    op.create_index(
        "uq_sample_custody_transfers_pending",
        "sample_custody_transfers",
        ["organization_id", "sample_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_sample_custody_transfers_pending", table_name="sample_custody_transfers")
    for column in ("organization_id", "sample_id", "from_user_id", "to_user_id", "status"):
        op.drop_index(f"ix_sample_custody_transfers_{column}", table_name="sample_custody_transfers")
    op.drop_table("sample_custody_transfers")
    op.drop_index("ix_samples_current_custodian_user_id", table_name="samples")
    op.drop_column("samples", "current_custodian_user_id")
