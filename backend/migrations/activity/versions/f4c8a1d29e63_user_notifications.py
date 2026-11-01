"""Add durable user notifications.

Revision ID: f4c8a1d29e63
Revises: e03d8c1f6a42
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4c8a1d29e63"
down_revision: Union[str, None] = "e03d8c1f6a42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("entity_type", sa.String(length=48), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", "event_id"),
    )
    for column in ("organization_id", "user_id", "event_id", "created_at", "read_at"):
        op.create_index(f"ix_notifications_{column}", "notifications", [column])


def downgrade() -> None:
    for column in ("read_at", "created_at", "event_id", "user_id", "organization_id"):
        op.drop_index(f"ix_notifications_{column}", table_name="notifications")
    op.drop_table("notifications")
