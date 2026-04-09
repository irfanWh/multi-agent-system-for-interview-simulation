from enum import Enum as PyEnum
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, 
    Enum, Text, Float
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base

def get_utc_now():
    return datetime.now(timezone.utc)

class ExperienceLevel(str, PyEnum):
    junior = "junior"
    mid = "mid"
    senior = "senior"
    lead = "lead"

class InterviewType(str, PyEnum):
    technical = "technical"
    behavioral = "behavioral"
    mixed = "mixed"

class SessionStatus(str, PyEnum):
    pending = "pending"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    profiles: Mapped[List["CandidateProfile"]] = relationship("CandidateProfile", back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    cv_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_role: Mapped[str] = mapped_column(String(255), nullable=False)
    experience_level: Mapped[ExperienceLevel] = mapped_column(Enum(ExperienceLevel), nullable=False)
    skills_extracted: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

    user: Mapped["User"] = relationship("User", back_populates="profiles")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="profile", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<CandidateProfile(id={self.id}, role={self.target_role}, xp={self.experience_level})>"

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="SET NULL"), nullable=True)
    interview_type: Mapped[InterviewType] = mapped_column(Enum(InterviewType), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.pending, nullable=False)
    session_plan: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="sessions")
    profile: Mapped[Optional["CandidateProfile"]] = relationship("CandidateProfile", back_populates="sessions")
    exchanges: Mapped[List["Exchange"]] = relationship("Exchange", back_populates="session", cascade="all, delete-orphan", order_by="Exchange.turn_number")
    report: Mapped[Optional["Report"]] = relationship("Report", back_populates="session", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, type={self.interview_type}, status={self.status})>"

class Exchange(Base):
    __tablename__ = "exchanges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audio_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    response_time_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

    session: Mapped["Session"] = relationship("Session", back_populates="exchanges")
    evaluation: Mapped[Optional["Evaluation"]] = relationship("Evaluation", back_populates="exchange", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Exchange(id={self.id}, session={self.session_id}, turn={self.turn_number})>"

class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exchange_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exchanges.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    score_accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_depth: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_clarity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_star: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    improvement_tips: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    exchange: Mapped["Exchange"] = relationship("Exchange", back_populates="evaluation")

    def __repr__(self) -> str:
        return f"<Evaluation(id={self.id}, exchange={self.exchange_id})>"

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    global_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    competency_breakdown: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    action_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)

    session: Mapped["Session"] = relationship("Session", back_populates="report")

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, session={self.session_id}, score={self.global_score})>"
