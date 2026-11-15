"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_admin', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('key_id', sa.String(64), unique=True, nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('scopes', sa.JSON, nullable=False, default=list),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('last_used_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('event_id', sa.String(36), unique=True, nullable=False),
        sa.Column('timestamp', sa.DateTime, server_default=sa.func.now()),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('level', sa.String(20), nullable=False),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('session_id', sa.String(64), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('request_id', sa.String(36), nullable=True),
        sa.Column('resource', sa.String(100), nullable=True),
        sa.Column('action', sa.String(100), nullable=True),
        sa.Column('outcome', sa.String(50), nullable=True),
        sa.Column('details', sa.JSON, nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
    )

    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_event_type', 'audit_logs', ['event_type'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_event_type', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_timestamp', table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_table('api_keys')
    op.drop_table('users')