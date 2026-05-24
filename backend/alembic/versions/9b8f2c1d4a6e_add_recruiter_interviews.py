"""add_recruiter_interviews

Revision ID: 9b8f2c1d4a6e
Revises: 0ea7778d0628
Create Date: 2026-05-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9b8f2c1d4a6e"
down_revision: Union[str, None] = "0ea7778d0628"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'scheduled'")
    op.execute("ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'in_progress'")
    op.execute("ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'expired'")

    op.create_table(
        "recruiter_interviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recruiter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role_title", sa.String(length=255), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column(
            "interview_type",
            postgresql.ENUM("technical", "behavioral", "mixed", name="interviewtype", create_type=False),
            nullable=False,
        ),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("code_hint", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "active",
                "completed",
                "cancelled",
                "scheduled",
                "in_progress",
                "expired",
                name="sessionstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("candidate_name", sa.String(length=255), nullable=True),
        sa.Column("candidate_email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recruiter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index(op.f("ix_recruiter_interviews_recruiter_id"), "recruiter_interviews", ["recruiter_id"], unique=False)
    op.create_index(op.f("ix_recruiter_interviews_resume_id"), "recruiter_interviews", ["resume_id"], unique=False)
    op.create_index(op.f("ix_recruiter_interviews_session_id"), "recruiter_interviews", ["session_id"], unique=False)
    op.create_index(op.f("ix_recruiter_interviews_code_hash"), "recruiter_interviews", ["code_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_recruiter_interviews_code_hash"), table_name="recruiter_interviews")
    op.drop_index(op.f("ix_recruiter_interviews_session_id"), table_name="recruiter_interviews")
    op.drop_index(op.f("ix_recruiter_interviews_resume_id"), table_name="recruiter_interviews")
    op.drop_index(op.f("ix_recruiter_interviews_recruiter_id"), table_name="recruiter_interviews")
    op.drop_table("recruiter_interviews")
