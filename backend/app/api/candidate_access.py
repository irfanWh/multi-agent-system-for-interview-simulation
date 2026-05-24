from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.orm import SessionStatus
from app.models.schemas import (
    AccessCodeRequest,
    CandidateAccessResponse,
    CandidateStartRequest,
    CandidateStartResponse,
)
from app.services.resume_service import ResumeService
from app.services.recruiter_interview_service import (
    build_session_for_recruiter_interview,
    get_interview_by_code,
)

router = APIRouter(prefix="/candidate-access", tags=["candidate-access"])

email_adapter = TypeAdapter(EmailStr)


def validate_candidate_identity(name: str | None, email: str | None) -> tuple[str, str]:
    clean_name = (name or "").strip()
    if len(clean_name) < 2:
        raise HTTPException(status_code=400, detail="Please enter the candidate's full name.")
    try:
        clean_email = str(email_adapter.validate_python(email or ""))
    except ValidationError:
        raise HTTPException(status_code=400, detail="Please enter a valid candidate email address.")
    return clean_name, clean_email


def _candidate_access_payload(interview) -> dict:
    resume = interview.resume
    return {
        "valid": True,
        "interview_id": interview.id,
        "role_title": interview.role_title,
        "interview_type": interview.interview_type,
        "duration_minutes": interview.duration_minutes,
        "deadline_at": interview.deadline_at,
        "status": interview.status,
        "resume_uploaded": bool(interview.resume_id),
        "resume_analyzed": bool(resume and resume.is_analyzed),
        "candidate_name": interview.candidate_name,
        "candidate_email": interview.candidate_email,
        "session_id": interview.session_id,
    }


@router.post("/validate", response_model=CandidateAccessResponse)
async def validate_access_code(
    payload: AccessCodeRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    interview = await get_interview_by_code(payload.code, db, require_available=False)
    if interview.status in {SessionStatus.completed, SessionStatus.expired, SessionStatus.cancelled}:
        raise HTTPException(status_code=400, detail=f"Interview is {interview.status.value}")
    return _candidate_access_payload(interview)


@router.post("/upload-resume", response_model=CandidateAccessResponse)
async def upload_candidate_resume(
    code: str = Form(...),
    candidate_name: str | None = Form(default=None),
    candidate_email: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> Any:
    interview = await get_interview_by_code(code, db)
    if interview.status in {SessionStatus.in_progress, SessionStatus.completed}:
        raise HTTPException(status_code=400, detail="Interview already started")

    if not file.filename or not file.filename.endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only PDF, DOCX, and TXT are allowed.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large")

    resume, _ = await ResumeService.upload_resume(
        user_id=str(interview.recruiter_id),
        file_bytes=file_bytes,
        filename=file.filename,
        db=db,
        is_recruiter_candidate=True,
    )

    clean_name, clean_email = validate_candidate_identity(
        candidate_name or interview.candidate_name,
        candidate_email or interview.candidate_email,
    )
    interview.resume_id = resume.id
    interview.candidate_name = clean_name
    interview.candidate_email = clean_email
    interview.status = SessionStatus.pending if not resume.is_analyzed else SessionStatus.scheduled
    await db.commit()
    refreshed = await get_interview_by_code(code, db, require_available=False)
    return _candidate_access_payload(refreshed)


@router.post("/start", response_model=CandidateStartResponse)
async def start_candidate_interview(
    payload: CandidateStartRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    interview = await get_interview_by_code(payload.code, db)
    clean_name, clean_email = validate_candidate_identity(
        payload.candidate_name or interview.candidate_name,
        str(payload.candidate_email or interview.candidate_email or ""),
    )
    interview.candidate_name = clean_name
    interview.candidate_email = clean_email

    session = await build_session_for_recruiter_interview(interview, db)
    await db.refresh(interview)
    return {"session_id": session.id, "status": interview.status}
