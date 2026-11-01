"""Allow the longest supported source.action event name.

Revision ID: e03d8c1f6a42
Revises: d24f87c3b1a0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e03d8c1f6a42"
down_revision: Union[str, None] = "d24f87c3b1a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "webhook_deliveries",
        "event_type",
        existing_type=sa.String(length=112),
        type_=sa.String(length=113),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "webhook_deliveries",
        "event_type",
        existing_type=sa.String(length=113),
        type_=sa.String(length=112),
        existing_nullable=False,
    )
