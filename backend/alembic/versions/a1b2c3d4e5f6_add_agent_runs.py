"""add agent_runs

Revision ID: a1b2c3d4e5f6
Revises: 6d114ed60f6e
Create Date: 2026-07-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6d114ed60f6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'running',
                'paused',
                'ready_for_review',
                'failed',
                'abandoned',
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            'pause_reason',
            sa.Enum(
                'login_required',
                'captcha',
                'unmapped_required_field',
                'cap_exceeded',
                'error',
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('action_log', sa.JSON(), nullable=True),
        sa.Column('llm_calls', sa.Integer(), nullable=False),
        sa.Column('screenshots_dir', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('agent_runs')
