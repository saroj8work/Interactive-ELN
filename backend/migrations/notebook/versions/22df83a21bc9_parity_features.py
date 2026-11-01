"""storage locations, workflow rules, and entry timestamps

Revision ID: 22df83a21bc9
Revises: 11ce01f7549b
Create Date: 2026-10-13 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '22df83a21bc9'
down_revision: Union[str, None] = '11ce01f7549b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create storage_locations
    op.create_table(
        'storage_locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('location_type', sa.String(length=32), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['storage_locations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'code')
    )
    with op.batch_alter_table('storage_locations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_storage_locations_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_storage_locations_parent_id'), ['parent_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_storage_locations_status'), ['status'], unique=False)

    # 2. Add location_id to inventory_items
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_inventory_items_location_id', 'storage_locations', ['location_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_inventory_items_location_id'), ['location_id'], unique=False)

    # 3. Add storage_location_id to samples
    with op.batch_alter_table('samples', schema=None) as batch_op:
        batch_op.add_column(sa.Column('storage_location_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_samples_storage_location_id', 'storage_locations', ['storage_location_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_samples_storage_location_id'), ['storage_location_id'], unique=False)

    # 4. Add storage_location_id to equipment_resources
    with op.batch_alter_table('equipment_resources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('storage_location_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_equipment_resources_storage_location_id', 'storage_locations', ['storage_location_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_equipment_resources_storage_location_id'), ['storage_location_id'], unique=False)

    # 5. Create workflow_rules
    op.create_table(
        'workflow_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('from_status', sa.String(length=32), nullable=True),
        sa.Column('to_status', sa.String(length=32), nullable=False),
        sa.Column('task_title', sa.String(length=200), nullable=False),
        sa.Column('task_description', sa.Text(), nullable=False),
        sa.Column('task_priority', sa.String(length=16), nullable=False),
        sa.Column('due_days', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('workflow_rules', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workflow_rules_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_rules_project_id'), ['project_id'], unique=False)

    # 6. Create workflow_executions
    op.create_table(
        'workflow_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=False),
        sa.Column('transition_id', sa.String(length=36), nullable=False),
        sa.Column('experiment_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['workflow_rules.id']),
        sa.ForeignKeyConstraint(['task_id'], ['lab_tasks.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'rule_id', 'transition_id')
    )
    with op.batch_alter_table('workflow_executions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workflow_executions_experiment_id'), ['experiment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_executions_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_executions_rule_id'), ['rule_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_executions_task_id'), ['task_id'], unique=False)

    # 7. Create entry_timestamps
    op.create_table(
        'entry_timestamps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('entry_id', sa.Integer(), nullable=False),
        sa.Column('requested_by_user_id', sa.Integer(), nullable=False),
        sa.Column('tsa_url', sa.String(length=500), nullable=False),
        sa.Column('record_sha256', sa.String(length=64), nullable=False),
        sa.Column('snapshot_json', sa.Text(), nullable=False),
        sa.Column('token_der', sa.LargeBinary(), nullable=False),
        sa.Column('tsa_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['entry_id'], ['notebook_entries.id']),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('entry_timestamps', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_entry_timestamps_entry_id'), ['entry_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_entry_timestamps_organization_id'), ['organization_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('entry_timestamps', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_entry_timestamps_organization_id'))
        batch_op.drop_index(batch_op.f('ix_entry_timestamps_entry_id'))
    op.drop_table('entry_timestamps')

    with op.batch_alter_table('workflow_executions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_workflow_executions_task_id'))
        batch_op.drop_index(batch_op.f('ix_workflow_executions_rule_id'))
        batch_op.drop_index(batch_op.f('ix_workflow_executions_organization_id'))
        batch_op.drop_index(batch_op.f('ix_workflow_executions_experiment_id'))
    op.drop_table('workflow_executions')

    with op.batch_alter_table('workflow_rules', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_workflow_rules_project_id'))
        batch_op.drop_index(batch_op.f('ix_workflow_rules_organization_id'))
    op.drop_table('workflow_rules')

    with op.batch_alter_table('equipment_resources', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_equipment_resources_storage_location_id'))
        batch_op.drop_constraint('fk_equipment_resources_storage_location_id', type_='foreignkey')
        batch_op.drop_column('storage_location_id')

    with op.batch_alter_table('samples', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_samples_storage_location_id'))
        batch_op.drop_constraint('fk_samples_storage_location_id', type_='foreignkey')
        batch_op.drop_column('storage_location_id')

    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_inventory_items_location_id'))
        batch_op.drop_constraint('fk_inventory_items_location_id', type_='foreignkey')
        batch_op.drop_column('location_id')

    with op.batch_alter_table('storage_locations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_storage_locations_status'))
        batch_op.drop_index(batch_op.f('ix_storage_locations_parent_id'))
        batch_op.drop_index(batch_op.f('ix_storage_locations_organization_id'))
    op.drop_table('storage_locations')

