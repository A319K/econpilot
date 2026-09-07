"""add answer_bank

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'answer_bank',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_norm', sa.String(length=512), nullable=False),
        sa.Column('question_raw', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('source', sa.Enum('user', 'llm', native_enum=False), nullable=False),
        sa.Column('approved', sa.Boolean(), nullable=False),
        sa.Column('times_used', sa.Integer(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('question_norm'),
    )
    op.create_index(op.f('ix_answer_bank_question_norm'), 'answer_bank', ['question_norm'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_answer_bank_question_norm'), table_name='answer_bank')
    op.drop_table('answer_bank')
