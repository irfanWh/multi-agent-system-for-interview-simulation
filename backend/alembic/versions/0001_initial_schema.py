"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-04-09 16:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # Create enums manually before referencing them in tables
    experience_enum = postgresql.ENUM('junior', 'mid', 'senior', 'lead', name='experiencelevel')
    experience_enum.create(op.get_bind())
    
    # 2. candidate_profiles
    op.create_table('candidate_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cv_text', sa.Text(), nullable=True),
        sa.Column('target_role', sa.String(length=255), nullable=False),
        sa.Column('experience_level', postgresql.ENUM('junior', 'mid', 'senior', 'lead', name='experiencelevel', create_type=False), nullable=False),
        sa.Column('skills_extracted', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('ix_candidate_profiles_user_id'), 'candidate_profiles', ['user_id'])
    
    interview_type_enum = postgresql.ENUM('technical', 'behavioral', 'mixed', name='interviewtype')
    interview_type_enum.create(op.get_bind())
    
    session_status_enum = postgresql.ENUM('pending', 'active', 'completed', 'cancelled', name='sessionstatus')
    session_status_enum.create(op.get_bind())

    # 3. sessions
    op.create_table('sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('profile_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('interview_type', postgresql.ENUM('technical', 'behavioral', 'mixed', name='interviewtype', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'active', 'completed', 'cancelled', name='sessionstatus', create_type=False), nullable=False),
        sa.Column('session_plan', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['candidate_profiles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'])

    # 4. exchanges
    op.create_table('exchanges',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('candidate_answer', sa.Text(), nullable=True),
        sa.Column('audio_url', sa.String(length=1024), nullable=True),
        sa.Column('response_time_sec', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('ix_exchanges_session_id'), 'exchanges', ['session_id'])

    # 5. evaluations
    op.create_table('evaluations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('exchange_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('score_accuracy', sa.Float(), nullable=True),
        sa.Column('score_depth', sa.Float(), nullable=True),
        sa.Column('score_clarity', sa.Float(), nullable=True),
        sa.Column('score_star', sa.Float(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('improvement_tips', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['exchange_id'], ['exchanges.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('ix_evaluations_exchange_id'), 'evaluations', ['exchange_id'], unique=True)

    # 6. reports
    op.create_table('reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('global_score', sa.Float(), nullable=True),
        sa.Column('competency_breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('action_plan', sa.Text(), nullable=True),
        sa.Column('pdf_url', sa.String(length=1024), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('ix_reports_session_id'), 'reports', ['session_id'], unique=True)


def downgrade() -> None:
    # 6
    op.drop_index(op.f('ix_reports_session_id'), table_name='reports')
    op.drop_table('reports')
    
    # 5
    op.drop_index(op.f('ix_evaluations_exchange_id'), table_name='evaluations')
    op.drop_table('evaluations')
    
    # 4
    op.drop_index(op.f('ix_exchanges_session_id'), table_name='exchanges')
    op.drop_table('exchanges')
    
    # 3
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_table('sessions')
    session_status_enum = postgresql.ENUM('pending', 'active', 'completed', 'cancelled', name='sessionstatus')
    session_status_enum.drop(op.get_bind())
    interview_type_enum = postgresql.ENUM('technical', 'behavioral', 'mixed', name='interviewtype')
    interview_type_enum.drop(op.get_bind())

    # 2
    op.drop_index(op.f('ix_candidate_profiles_user_id'), table_name='candidate_profiles')
    op.drop_table('candidate_profiles')
    experience_enum = postgresql.ENUM('junior', 'mid', 'senior', 'lead', name='experiencelevel')
    experience_enum.drop(op.get_bind())
    
    # 1
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
