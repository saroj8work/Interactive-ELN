"""Add GIN index for PostgreSQL project search.

Revision ID: c6b42e91a307
Revises: 4389fc7b4469
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c6b42e91a307"
down_revision: Union[str, None] = "4389fc7b4469"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_projects_search_document ON projects USING GIN "
        "(to_tsvector('simple'::regconfig, COALESCE(name, '') || ' ' || "
        "COALESCE(description, '')))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_projects_search_document")
