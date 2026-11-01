"""Add organization webhook endpoints and durable delivery queue.

Revision ID: d24f87c3b1a0
Revises: 3a3ec5e04473
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d24f87c3b1a0"
down_revision: Union[str, None] = "3a3ec5e04473"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("event_types", sa.JSON(), nullable=False),
        sa.Column("secret_prefix", sa.String(length=24), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_endpoints_organization_id", "webhook_endpoints", ["organization_id"])
    op.create_index("ix_webhook_endpoints_enabled", "webhook_endpoints", ["enabled"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("endpoint_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=112), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["endpoint_id"], ["webhook_endpoints.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint_id", "event_id", name="uq_webhook_delivery_endpoint_event"),
    )
    op.create_index("ix_webhook_deliveries_organization_id", "webhook_deliveries", ["organization_id"])
    op.create_index("ix_webhook_deliveries_endpoint_id", "webhook_deliveries", ["endpoint_id"])
    op.create_index("ix_webhook_deliveries_event_id", "webhook_deliveries", ["event_id"])
    op.create_index("ix_webhook_deliveries_next_attempt_at", "webhook_deliveries", ["next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_next_attempt_at", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_event_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_endpoint_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_organization_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_webhook_endpoints_enabled", table_name="webhook_endpoints")
    op.drop_index("ix_webhook_endpoints_organization_id", table_name="webhook_endpoints")
    op.drop_table("webhook_endpoints")
