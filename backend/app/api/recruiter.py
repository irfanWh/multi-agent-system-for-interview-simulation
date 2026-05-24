import uuid
from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_user
from app.api.resumes import validate_job_description
from app.models.orm import User, RecruiterInterview, Session, Report, SessionStatus
from app.models.schemas import RecruiterInterviewCreate, RecruiterInterviewResponse
from app.services.recruiter_interview_service import (
    generate_access_code,
    hash_access_code,
    normalize_code,
    serialize_recruiter_interview,
)

router = APIRouter(prefix="/recruiter", tags=["recruiter"])


@router.post("/sessions", response_model=RecruiterInterviewResponse, status_code=status.HTTP_201_CREATED)
async def create_recruiter_session(
    payload: RecruiterInterviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if payload.deadline_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Deadline must be in the future")
    validation_error = validate_job_description(payload.job_description)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    access_code = generate_access_code()
    code_hash = hash_access_code(access_code)
    while await db.scalar(select(RecruiterInterview).where(RecruiterInterview.code_hash == code_hash)):
        access_code = generate_access_code()
        code_hash = hash_access_code(access_code)

    interview = RecruiterInterview(
        recruiter_id=current_user.id,
        role_title=payload.role_title.strip(),
        job_description=payload.job_description.strip(),
        interview_type=payload.interview_type,
        duration_minutes=payload.duration_minutes,
        deadline_at=payload.deadline_at,
        candidate_name=payload.candidate_name.strip(),
        candidate_email=str(payload.candidate_email),
        code_hash=code_hash,
        code_hint=normalize_code(access_code)[-4:],
        status=SessionStatus.scheduled,
    )
    db.add(interview)
    await db.commit()
    await db.refresh(interview)
    return serialize_recruiter_interview(interview, access_code=access_code)


@router.get("/sessions", response_model=list[RecruiterInterviewResponse])
async def list_recruiter_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    result = await db.execute(
        select(RecruiterInterview)
        .options(selectinload(RecruiterInterview.session).selectinload(Session.report))
        .where(RecruiterInterview.recruiter_id == current_user.id)
        .order_by(RecruiterInterview.created_at.desc())
    )
    interviews = result.scalars().all()
    return [serialize_recruiter_interview(interview) for interview in interviews]


@router.get("/sessions/{interview_id}", response_model=RecruiterInterviewResponse)
async def get_recruiter_session(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    interview = await db.scalar(
        select(RecruiterInterview)
        .options(selectinload(RecruiterInterview.session).selectinload(Session.report))
        .where(
            RecruiterInterview.id == interview_id,
            RecruiterInterview.recruiter_id == current_user.id,
        )
    )
    if not interview:
        raise HTTPException(status_code=404, detail="Recruiter interview not found")
    return serialize_recruiter_interview(interview)


@router.post("/sessions/{interview_id}/regenerate-code", response_model=RecruiterInterviewResponse)
async def regenerate_code(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    interview = await db.scalar(
        select(RecruiterInterview).where(
            RecruiterInterview.id == interview_id,
            RecruiterInterview.recruiter_id == current_user.id,
        )
    )
    if not interview:
        raise HTTPException(status_code=404, detail="Recruiter interview not found")
    if interview.status in {SessionStatus.completed, SessionStatus.in_progress}:
        raise HTTPException(status_code=400, detail="Cannot regenerate code for this interview status")

    access_code = generate_access_code()
    code_hash = hash_access_code(access_code)
    while await db.scalar(select(RecruiterInterview).where(RecruiterInterview.code_hash == code_hash)):
        access_code = generate_access_code()
        code_hash = hash_access_code(access_code)

    interview.code_hash = code_hash
    interview.code_hint = normalize_code(access_code)[-4:]
    await db.commit()
    await db.refresh(interview)
    return serialize_recruiter_interview(interview, access_code=access_code)


@router.get("/sessions/{interview_id}/report")
async def get_recruiter_report(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    interview = await db.scalar(
        select(RecruiterInterview).where(
            RecruiterInterview.id == interview_id,
            RecruiterInterview.recruiter_id == current_user.id,
        )
    )
    if not interview:
        raise HTTPException(status_code=404, detail="Recruiter interview not found")
    if not interview.session_id:
        raise HTTPException(status_code=404, detail="Candidate has not started this interview yet")

    report = await db.scalar(select(Report).where(Report.session_id == interview.session_id))
    if not report:
        raise HTTPException(status_code=404, detail="Report not ready yet")

    import json
    action_plan = report.action_plan
    if isinstance(action_plan, str):
        try:
            action_plan = json.loads(action_plan)
        except (json.JSONDecodeError, TypeError):
            action_plan = []

    return {
        "id": str(report.id),
        "session_id": str(report.session_id),
        "global_score": report.global_score,
        "competency_breakdown": report.competency_breakdown,
        "action_plan": action_plan,
        "pdf_url": report.pdf_url,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }
