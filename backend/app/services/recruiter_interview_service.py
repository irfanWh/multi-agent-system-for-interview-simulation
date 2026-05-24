import hashlib
import secrets
import string
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.orm import RecruiterInterview, Session, SessionStatus, Resume
from app.api.resumes import validate_job_description
from app.services.resume_service import ResumeService


CODE_ALPHABET = string.ascii_uppercase + string.digits


def normalize_code(code: str) -> str:
    return code.strip().upper().replace("-", "").replace(" ", "")


def hash_access_code(code: str) -> str:
    normalized = normalize_code(code)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_access_code(length: int = 10) -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))
    return f"{raw[:4]}-{raw[4:7]}-{raw[7:]}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def get_interview_by_code(
    code: str,
    db: AsyncSession,
    *,
    require_available: bool = True,
) -> RecruiterInterview:
    interview = await db.scalar(
        select(RecruiterInterview)
        .options(
            selectinload(RecruiterInterview.resume),
            selectinload(RecruiterInterview.session).selectinload(Session.report),
        )
        .where(RecruiterInterview.code_hash == hash_access_code(code))
    )
    if not interview:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid interview code")

    if interview.deadline_at and interview.deadline_at < utc_now() and interview.status != SessionStatus.completed:
        interview.status = SessionStatus.expired
        if interview.session_id:
            session = await db.get(Session, interview.session_id)
            if session and session.status not in {SessionStatus.completed, SessionStatus.cancelled}:
                session.status = SessionStatus.expired
        await db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Interview code has expired")

    if require_available and interview.status in {SessionStatus.completed, SessionStatus.expired, SessionStatus.cancelled}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Interview is {interview.status.value}")

    return interview


def serialize_recruiter_interview(interview: RecruiterInterview, access_code: Optional[str] = None) -> dict:
    session = interview.__dict__.get("session")
    report_ready = bool(session and session.__dict__.get("report"))
    return {
        "id": interview.id,
        "role_title": interview.role_title,
        "job_description": interview.job_description,
        "interview_type": interview.interview_type,
        "duration_minutes": interview.duration_minutes,
        "deadline_at": interview.deadline_at,
        "status": interview.status,
        "code_hint": interview.code_hint,
        "access_code": access_code,
        "candidate_name": interview.candidate_name,
        "candidate_email": interview.candidate_email,
        "resume_id": interview.resume_id,
        "session_id": interview.session_id,
        "report_ready": report_ready,
        "created_at": interview.created_at,
        "updated_at": interview.updated_at,
    }


async def build_session_for_recruiter_interview(
    interview: RecruiterInterview,
    db: AsyncSession,
) -> Session:
    if interview.session_id:
        session = await db.get(Session, interview.session_id)
        if session:
            return session

    if not interview.resume_id:
        raise HTTPException(status_code=400, detail="candidate_resume_required")

    resume = await db.get(Resume, interview.resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Candidate resume not found")
    if not resume.is_analyzed:
        raise HTTPException(status_code=400, detail="resume_still_processing")

    validation_error = validate_job_description(interview.job_description)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    match_report, _ = await ResumeService.get_match_analysis(
        resume_id=str(resume.id),
        job_description=interview.job_description,
        db=db,
    )

    from app.agents.interview_planner import run_interview_planner
    from app.agents.orchestrator import run_orchestrator

    plan_result = await run_interview_planner(
        cv_text=resume.cv_text,
        job_description=interview.job_description,
        match_report=match_report,
        interview_config={
            "interview_type": interview.interview_type.value,
            "duration": interview.duration_minutes,
            "focus_areas": [],
        },
        previously_used_openers=[],
    )
    if plan_result.get("error"):
        raise HTTPException(status_code=500, detail=plan_result["error"])

    planner_session_plan = plan_result.get("interview_plan")
    job_profile = {
        "calibrated_level": resume.analyzed_profile.get("experience_level", "junior") if resume.analyzed_profile else "junior",
        "priority_domains": [],
    }
    orchestrator_result = await run_orchestrator(
        planner_output=planner_session_plan,
        job_profile=job_profile,
    )
    session_plan = planner_session_plan if orchestrator_result.get("error") else orchestrator_result.get("session_plan")

    session = Session(
        user_id=interview.recruiter_id,
        resume_id=resume.id,
        job_description=interview.job_description,
        interview_type=interview.interview_type,
        status=SessionStatus.scheduled,
        session_plan=session_plan,
    )
    db.add(session)
    await db.flush()

    interview.session_id = session.id
    interview.status = SessionStatus.scheduled
    await db.commit()
    await db.refresh(session)
    await db.refresh(interview)
    return session
