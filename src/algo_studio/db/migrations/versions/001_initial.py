"""Initial migration: enable WAL mode and create base tables

Revision ID: 001_initial
Revises:
Create Date: 2026-03-26

This migration:
1. Enables WAL (Write-Ahead Logging) mode for SQLite for better concurrency
2. Creates base tables: users, tasks, quotas, quota_usages, quota_alerts
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable WAL mode for better concurrency
    op.execute("PRAGMA journal_mode=WAL")

    # Create users table (RBAC ready)
    op.create_table(
        'users',
        sa.Column('user_id', sa.String(64), primary_key=True),
        sa.Column('username', sa.String(100), unique=True, nullable=False),
        sa.Column('email', sa.String(255), unique=True),
        sa.Column('password_hash', sa.String(255)),
        sa.Column('role', sa.String(20), default='viewer'),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_superuser', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
    )
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_email', 'users', ['email'])

    # Create tasks table (task history)
    op.create_table(
        'tasks',
        sa.Column('task_id', sa.String(64), primary_key=True),
        sa.Column('task_type', sa.String(20), nullable=False),  # train/infer/verify
        sa.Column('algorithm_name', sa.String(100), nullable=False),
        sa.Column('algorithm_version', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),  # pending/running/completed/failed/cancelled
        sa.Column('config', sa.JSON),
        sa.Column('result', sa.JSON),
        sa.Column('error', sa.Text),
        sa.Column('assigned_node', sa.String(100)),
        sa.Column('user_id', sa.String(64), sa.ForeignKey('users.user_id', ondelete='SET NULL')),
        sa.Column('progress', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime),
        sa.Column('completed_at', sa.DateTime),
    )
    op.create_index('idx_tasks_status', 'tasks', ['status'])
    op.create_index('idx_tasks_user', 'tasks', ['user_id'])
    op.create_index('idx_tasks_created', 'tasks', ['created_at'])

    # Create quotas table
    op.create_table(
        'quotas',
        sa.Column('quota_id', sa.String(64), primary_key=True),
        sa.Column('scope', sa.String(20), nullable=False),  # user/team/global
        sa.Column('scope_id', sa.String(64), nullable=False),  # user_id or team_id
        sa.Column('name', sa.String(100), nullable=False),
        # Limits
        sa.Column('cpu_cores', sa.Integer, default=0),
        sa.Column('gpu_count', sa.Integer, default=0),
        sa.Column('gpu_memory_gb', sa.Float, default=0.0),
        sa.Column('memory_gb', sa.Float, default=0.0),
        sa.Column('disk_gb', sa.Float, default=0.0),
        sa.Column('concurrent_tasks', sa.Integer, default=0),
        sa.Column('tasks_per_day', sa.Integer, default=50),
        sa.Column('gpu_hours_per_day', sa.Float, default=24.0),
        # Alert
        sa.Column('alert_threshold', sa.Integer, default=80),
        # Inheritance
        sa.Column('parent_quota_id', sa.String(64)),
        # Status
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
    )
    op.create_index('idx_quotas_scope', 'quotas', ['scope', 'scope_id'])

    # Create quota_usages table
    op.create_table(
        'quota_usages',
        sa.Column('quota_id', sa.String(64), sa.ForeignKey('quotas.quota_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('cpu_cores_used', sa.Float, default=0.0),
        sa.Column('gpu_count_used', sa.Integer, default=0),
        sa.Column('gpu_memory_gb_used', sa.Float, default=0.0),
        sa.Column('memory_gb_used', sa.Float, default=0.0),
        sa.Column('disk_gb_used', sa.Float, default=0.0),
        sa.Column('concurrent_tasks_used', sa.Integer, default=0),
        sa.Column('tasks_today', sa.Integer, default=0),
        sa.Column('gpu_minutes_today', sa.Float, default=0.0),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create quota_usage_history table (for statistics)
    op.create_table(
        'quota_usage_history',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('quota_id', sa.String(64), sa.ForeignKey('quotas.quota_id', ondelete='CASCADE')),
        sa.Column('metric', sa.String(50), nullable=False),
        sa.Column('value', sa.Float, nullable=False),
        sa.Column('recorded_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_usage_history_quota', 'quota_usage_history', ['quota_id'])
    op.create_index('idx_usage_history_recorded', 'quota_usage_history', ['recorded_at'])

    # Create quota_alerts table
    op.create_table(
        'quota_alerts',
        sa.Column('alert_id', sa.String(64), primary_key=True),
        sa.Column('quota_id', sa.String(64), sa.ForeignKey('quotas.quota_id', ondelete='CASCADE')),
        sa.Column('scope', sa.String(20), nullable=False),
        sa.Column('scope_id', sa.String(64), nullable=False),
        sa.Column('level', sa.String(20), nullable=False),  # info/warning/critical
        sa.Column('metric', sa.String(50), nullable=False),
        sa.Column('usage_percentage', sa.Float, nullable=False),
        sa.Column('threshold', sa.Integer, nullable=False),
        sa.Column('message', sa.Text),
        sa.Column('task_id', sa.String(64)),  # Associated task for queue wait alerts
        sa.Column('is_acknowledged', sa.Boolean, default=False),
        sa.Column('acknowledged_by', sa.String(64)),
        sa.Column('acknowledged_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_alerts_quota', 'quota_alerts', ['quota_id'])
    op.create_index('idx_alerts_created', 'quota_alerts', ['created_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('quota_alerts')
    op.drop_table('quota_usage_history')
    op.drop_table('quota_usages')
    op.drop_table('quotas')
    op.drop_table('tasks')
    op.drop_table('users')
