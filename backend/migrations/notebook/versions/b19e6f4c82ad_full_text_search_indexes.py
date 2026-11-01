"""Add GIN indexes for PostgreSQL notebook search.

Revision ID: b19e6f4c82ad
Revises: 22df83a21bc9
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b19e6f4c82ad"
down_revision: Union[str, None] = "22df83a21bc9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEARCH_INDEXES = (
    (
        "ix_experiments_search_document",
        "experiments",
        "to_tsvector('simple'::regconfig, COALESCE(name, '') || ' ' || COALESCE(description, ''))",
    ),
    (
        "ix_notebook_entries_search_document",
        "notebook_entries",
        "to_tsvector('simple'::regconfig, COALESCE(title, '') || ' ' || COALESCE(content, ''))",
    ),
    (
        "ix_inventory_items_search_document",
        "inventory_items",
        "to_tsvector('simple'::regconfig, COALESCE(name, '') || ' ' || COALESCE(category, '') || ' ' || COALESCE(catalog_number, '') || ' ' || COALESCE(lot_number, '') || ' ' || COALESCE(location, '') || ' ' || COALESCE(notes, ''))",
    ),
    (
        "ix_samples_search_document",
        "samples",
        "to_tsvector('simple'::regconfig, COALESCE(name, '') || ' ' || COALESCE(external_id, '') || ' ' || COALESCE(sample_type, '') || ' ' || COALESCE(storage_location, '') || ' ' || COALESCE(description, ''))",
    ),
    (
        "ix_equipment_resources_search_document",
        "equipment_resources",
        "to_tsvector('simple'::regconfig, COALESCE(name, '') || ' ' || COALESCE(location, '') || ' ' || COALESCE(category, '') || ' ' || COALESCE(description, ''))",
    ),
    (
        "ix_notebook_templates_search_document",
        "notebook_templates",
        "to_tsvector('simple'::regconfig, COALESCE(name, '') || ' ' || COALESCE(description, ''))",
    ),
    (
        "ix_record_tags_search_document",
        "record_tags",
        "to_tsvector('simple'::regconfig, COALESCE(tag, ''))",
    ),
)


def upgrade() -> None:
    for index_name, table_name, expression in SEARCH_INDEXES:
        op.execute(
            f"CREATE INDEX {index_name} ON {table_name} USING GIN ({expression})"
        )


def downgrade() -> None:
    for index_name, _, _ in reversed(SEARCH_INDEXES):
        op.execute(f"DROP INDEX {index_name}")
