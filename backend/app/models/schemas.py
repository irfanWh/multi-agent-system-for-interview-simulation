from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

from app.models.orm import ExperienceLevel, InterviewType, SessionStatus

# ==============================================================================
# USER SCHEMAS
# ==============================================================================
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# CANDIDATE PROFILE SCHEMAS
# ==============================================================================
class CandidateProfileBase(BaseModel):
    target_role: str
    experience_level: ExperienceLevel
    cv_text: Optional[str] = None
    skills_extracted: Optional[Dict[str, Any]] = None

class CandidateProfileCreate(CandidateProfileBase):
    user_id: UUID

class CandidateProfileUpdate(BaseModel):
    target_role: Optional[str] = None
    experience_level: Optional[ExperienceLevel] = None
    cv_text: Optional[str] = None
    skills_extracted: Optional[Dict[str, Any]] = None

class CandidateProfileResponse(CandidateProfileBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# SESSION SCHEMAS
# ==============================================================================
class SessionBase(BaseModel):
    interview_type: InterviewType
    status: SessionStatus = SessionStatus.pending
    session_plan: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

class SessionCreate(SessionBase):
    user_id: UUID
    profile_id: Optional[UUID] = None

class SessionUpdate(BaseModel):
    status: Optional[SessionStatus] = None
    session_plan: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

class SessionResponse(SessionBase):
    id: UUID
    user_id: UUID
    profile_id: Optional[UUID] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# EXCHANGE SCHEMAS
# ==============================================================================
class ExchangeBase(BaseModel):
    turn_number: int
    question: str
    candidate_answer: Optional[str] = None
    audio_url: Optional[str] = None
    response_time_sec: Optional[float] = None

class ExchangeCreate(ExchangeBase):
    session_id: UUID

class ExchangeUpdate(BaseModel):
    candidate_answer: Optional[str] = None
    audio_url: Optional[str] = None
    response_time_sec: Optional[float] = None

class ExchangeResponse(ExchangeBase):
    id: UUID
    session_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# EVALUATION SCHEMAS
# ==============================================================================
class EvaluationBase(BaseModel):
    score_accuracy: Optional[float] = Field(None, ge=0, le=10)
    score_depth: Optional[float] = Field(None, ge=0, le=10)
    score_clarity: Optional[float] = Field(None, ge=0, le=10)
    score_star: Optional[float] = Field(None, ge=0, le=10)
    feedback: Optional[str] = None
    improvement_tips: Optional[Dict[str, Any]] = None

class EvaluationCreate(EvaluationBase):
    exchange_id: UUID

class EvaluationUpdate(EvaluationBase):
    score_accuracy: Optional[float] = Field(None, ge=0, le=10)
    score_depth: Optional[float] = Field(None, ge=0, le=10)
    score_clarity: Optional[float] = Field(None, ge=0, le=10)
    score_star: Optional[float] = Field(None, ge=0, le=10)
    feedback: Optional[str] = None
    improvement_tips: Optional[Dict[str, Any]] = None

class EvaluationResponse(EvaluationBase):
    id: UUID
    exchange_id: UUID
    
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# REPORT SCHEMAS
# ==============================================================================
class ReportBase(BaseModel):
    global_score: Optional[float] = Field(None, ge=0, le=10)
    competency_breakdown: Optional[Dict[str, Any]] = None
    action_plan: Optional[str] = None
    pdf_url: Optional[str] = None

class ReportCreate(ReportBase):
    session_id: UUID

class ReportUpdate(ReportBase):
    global_score: Optional[float] = Field(None, ge=0, le=10)
    competency_breakdown: Optional[Dict[str, Any]] = None
    action_plan: Optional[str] = None
    pdf_url: Optional[str] = None

class ReportResponse(ReportBase):
    id: UUID
    session_id: UUID
    generated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
