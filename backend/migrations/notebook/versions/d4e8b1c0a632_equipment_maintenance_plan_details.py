"""Add maintenance plan end date and provider contacts.

Revision ID: d4e8b1c0a632
Revises: c31ad9e5b204
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e8b1c0a632"
down_revision: Union[str, None] = "c31ad9e5b204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("equipment_maintenance", sa.Column("service_contact_email", sa.String(length=320), nullable=False, server_default=""))
    op.add_column("equipment_maintenance", sa.Column("service_contact_phone", sa.String(length=64), nullable=False, server_default=""))
    op.add_column("equipment_maintenance", sa.Column("recurrence_until", sa.Date(), nullable=True))
    op.alter_column("equipment_maintenance", "service_contact_email", server_default=None)
    op.alter_column("equipment_maintenance", "service_contact_phone", server_default=None)


def downgrade() -> None:
    op.drop_column("equipment_maintenance", "recurrence_until")
    op.drop_column("equipment_maintenance", "service_contact_phone")
    op.drop_column("equipment_maintenance", "service_contact_email")
