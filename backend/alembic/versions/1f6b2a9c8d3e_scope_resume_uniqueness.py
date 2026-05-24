"""scope_resume_uniqueness

Revision ID: 1f6b2a9c8d3e
Revises: c7a4e9d2b1f0
Create Date: 2026-05-24 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "1f6b2a9c8d3e"
down_revision: Union[str, None] = "c7a4e9d2b1f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("resumes_user_id_file_hash_key", "resumes", type_="unique")
    op.create_unique_constraint(
        "uq_resumes_user_hash_recruiter_scope",
        "resumes",
        ["user_id", "file_hash", "is_recruiter_candidate"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_resumes_user_hash_recruiter_scope", "resumes", type_="unique")
    op.create_unique_constraint(
        "resumes_user_id_file_hash_key",
        "resumes",
        ["user_id", "file_hash"],
    )
