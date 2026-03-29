"""Add datasets table

Revision ID: 002_add_datasets
Revises: 001_initial
Create Date: 2026-03-29

This migration:
1. Creates datasets table for dataset metadata storage
2. Creates dataset_access table for access control
3. Adds dataset_id column to tasks table (FK enforced at ORM level for SQLite)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002_add_datasets'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create datasets table
    op.create_table(
        'datasets',
        sa.Column('dataset_id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(255), unique=True, nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('path', sa.String(512), nullable=False),
        sa.Column('storage_type', sa.String(20), default='dvc'),
        sa.Column('size_gb', sa.Float),
        sa.Column('file_count', sa.Integer),
        sa.Column('version', sa.String(64)),
        sa.Column('dvc_path', sa.String(512)),
        sa.Column('extra_metadata', sa.JSON),
        sa.Column('tags', sa.JSON),
        sa.Column('is_public', sa.Boolean, default=False),
        sa.Column('owner_id', sa.String(64), sa.ForeignKey('users.user_id', ondelete='SET NULL')),
        # team_id FK commented out - teams table not yet migrated
        # sa.Column('team_id', sa.String(64), sa.ForeignKey('teams.team_id', ondelete='SET NULL')),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('last_accessed_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
    )
    op.create_index('idx_datasets_name', 'datasets', ['name'])
    op.create_index('idx_datasets_owner', 'datasets', ['owner_id'])
    op.create_index('idx_datasets_is_active', 'datasets', ['is_active'])

    # Create dataset_access table
    op.create_table(
        'dataset_access',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('dataset_id', sa.String(64), sa.ForeignKey('datasets.dataset_id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(64), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=True),
        # team_id FK commented out - teams table not yet migrated
        # sa.Column('team_id', sa.String(64), sa.ForeignKey('teams.team_id', ondelete='CASCADE'), nullable=True),
        sa.Column('access_level', sa.String(20), default='read'),
        sa.Column('granted_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('granted_by', sa.String(64)),
    )
    op.create_index('idx_dataset_access_dataset', 'dataset_access', ['dataset_id'])
    op.create_index('idx_dataset_access_user', 'dataset_access', ['user_id'])

    # Add dataset_id column to tasks table
    # Note: FK constraint is not added here because SQLite doesn't support
    # ALTER TABLE ADD CONSTRAINT. The FK is enforced at the ORM level.
    op.add_column('tasks', sa.Column('dataset_id', sa.String(64), nullable=True))
    op.create_index('idx_tasks_dataset', 'tasks', ['dataset_id'])


def downgrade() -> None:
    op.drop_index('idx_tasks_dataset', 'tasks')
    op.drop_column('tasks', 'dataset_id')
    op.drop_table('dataset_access')
    op.drop_table('datasets')
