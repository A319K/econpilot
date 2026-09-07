"""allow uploaded resumes

Base resumes may now be a PDF the user dragged in rather than a LaTeX
template we compile, so latex_source becomes nullable and we keep the
original filename to show them which file it was.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite can't ALTER a column's nullability in place; batch mode rebuilds
    # the table around the change.
    with op.batch_alter_table("resume_versions") as batch_op:
        batch_op.alter_column("latex_source", existing_type=sa.Text(), nullable=True)
        batch_op.add_column(sa.Column("original_filename", sa.String(length=255), nullable=True))


def downgrade() -> None:
    # Uploaded resumes have no LaTeX to restore, so they'd violate the
    # re-imposed NOT NULL. Give them an empty source rather than fail.
    op.execute("UPDATE resume_versions SET latex_source = '' WHERE latex_source IS NULL")
    with op.batch_alter_table("resume_versions") as batch_op:
        batch_op.drop_column("original_filename")
        batch_op.alter_column("latex_source", existing_type=sa.Text(), nullable=False)
