"""add ats_probed_at to company

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # When we last actively probed an unknown-ATS company against the job-board
    # APIs. Lets the auto-resolver skip companies it has already checked instead
    # of re-probing every scan.
    op.add_column('companies', sa.Column('ats_probed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('companies', 'ats_probed_at')
