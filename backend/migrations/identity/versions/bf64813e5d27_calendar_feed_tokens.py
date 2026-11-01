"""Add revocable read-only calendar feed tokens.

Revision ID: bf64813e5d27
Revises: d53f812b147a
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bf64813e5d27"
down_revision: Union[str, None] = "d53f812b147a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calendar_feeds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_calendar_feeds_organization_id", "calendar_feeds", ["organization_id"])
    op.create_index("ix_calendar_feeds_user_id", "calendar_feeds", ["user_id"])
    op.create_index("ix_calendar_feeds_token_prefix", "calendar_feeds", ["token_prefix"])


def downgrade() -> None:
    op.drop_index("ix_calendar_feeds_token_prefix", table_name="calendar_feeds")
    op.drop_index("ix_calendar_feeds_user_id", table_name="calendar_feeds")
    op.drop_index("ix_calendar_feeds_organization_id", table_name="calendar_feeds")
    op.drop_table("calendar_feeds")
