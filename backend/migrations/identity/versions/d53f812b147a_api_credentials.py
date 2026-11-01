"""Add user-managed API credentials.

Revision ID: d53f812b147a
Revises: aec06942ec4f
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d53f812b147a"
down_revision: Union[str, None] = "aec06942ec4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=24), nullable=False),
        sa.Column("scopes", sa.String(length=200), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_api_credentials_organization_id", "api_credentials", ["organization_id"])
    op.create_index("ix_api_credentials_user_id", "api_credentials", ["user_id"])
    op.create_index("ix_api_credentials_token_prefix", "api_credentials", ["token_prefix"])


def downgrade() -> None:
    op.drop_index("ix_api_credentials_token_prefix", table_name="api_credentials")
    op.drop_index("ix_api_credentials_user_id", table_name="api_credentials")
    op.drop_index("ix_api_credentials_organization_id", table_name="api_credentials")
    op.drop_table("api_credentials")
