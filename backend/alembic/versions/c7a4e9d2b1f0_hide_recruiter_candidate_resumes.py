"""hide_recruiter_candidate_resumes

Revision ID: c7a4e9d2b1f0
Revises: 9b8f2c1d4a6e
Create Date: 2026-05-24 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7a4e9d2b1f0"
down_revision: Union[str, None] = "9b8f2c1d4a6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resumes",
        sa.Column("is_recruiter_candidate", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("resumes", "is_recruiter_candidate")
