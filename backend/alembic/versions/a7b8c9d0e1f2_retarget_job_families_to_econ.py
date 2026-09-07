"""retarget job families to economics roles

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_FAMILIES = sa.Enum("swe", "data", "cloud_infra", "ml", "other", name="jobfamily", native_enum=False)
NEW_FAMILIES = sa.Enum(
    "finance",
    "consulting",
    "data_analytics",
    "corporate",
    "policy_research",
    "other",
    name="jobfamily",
    native_enum=False,
)


def upgrade() -> None:
    # Preserve useful data-oriented records; obsolete engineering families can
    # no longer be classified safely and become "other" for manual review.
    op.execute("UPDATE jobs SET job_family = 'data_analytics' WHERE job_family IN ('data', 'ml')")
    op.execute("UPDATE jobs SET job_family = 'other' WHERE job_family IN ('swe', 'cloud_infra')")
    op.execute(
        "UPDATE resume_versions SET job_family = 'data_analytics' "
        "WHERE job_family IN ('data', 'ml')"
    )
    op.execute(
        "UPDATE resume_versions SET job_family = 'other' "
        "WHERE job_family IN ('swe', 'cloud_infra')"
    )
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.alter_column("job_family", existing_type=OLD_FAMILIES, type_=NEW_FAMILIES)
    with op.batch_alter_table("resume_versions") as batch_op:
        batch_op.alter_column("job_family", existing_type=OLD_FAMILIES, type_=NEW_FAMILIES)


def downgrade() -> None:
    op.execute("UPDATE jobs SET job_family = 'data' WHERE job_family = 'data_analytics'")
    op.execute("UPDATE jobs SET job_family = 'swe' WHERE job_family != 'data'")
    op.execute("UPDATE resume_versions SET job_family = 'data' WHERE job_family = 'data_analytics'")
    op.execute("UPDATE resume_versions SET job_family = 'swe' WHERE job_family != 'data'")
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.alter_column("job_family", existing_type=NEW_FAMILIES, type_=OLD_FAMILIES)
    with op.batch_alter_table("resume_versions") as batch_op:
        batch_op.alter_column("job_family", existing_type=NEW_FAMILIES, type_=OLD_FAMILIES)
