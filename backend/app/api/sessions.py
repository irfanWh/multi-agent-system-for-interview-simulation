import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import get_db, get_current_user
from app.api.resumes import validate_job_description
from app.models.orm import Session, User, Resume
from app.services.resume_service import ResumeService
from app.models.schemas import SessionCreate, SessionResponse, SessionUpdate

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    duration_minutes: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create a new interview session.
    Runs Profile Analyzer (if needed) + Orchestrator to generate SessionPlan.
    """
    # 1. Fetch related resume
    if not session_data.resume_id:
        raise HTTPException(status_code=400, detail="resume_id is required")
        
    resume = await db.get(Resume, str(session_data.resume_id))
    if not resume or str(resume.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Resume not found")
        
    if not resume.is_analyzed:
        raise HTTPException(status_code=400, detail="resume_still_processing")
        
    match_report = None
    if session_data.job_description:
        validation_error = validate_job_description(session_data.job_description)
        if validation_error:
            raise HTTPException(status_code=400, detail=validation_error)
            
        match_report_dict, was_cached = await ResumeService.get_match_analysis(
            resume_id=str(resume.id),
            job_description=session_data.job_description,
            db=db
        )
        match_report = match_report_dict

    # 3. Run Agent 2 — InterviewPlanner
    from app.agents.interview_planner import run_interview_planner
    
    # Fetch previously used openers
    past_sessions_query = await db.execute(
        select(Session).where(
            Session.resume_id == resume.id,
            Session.user_id == current_user.id
        )
    )
    past_sessions = past_sessions_query.scalars().all()
    
    previously_used_openers = []
    for s in past_sessions:
        if s.session_plan and "opening_anchor_id" in s.session_plan:
            opening_id = s.session_plan["opening_anchor_id"]
            # find title
            for anchor in s.session_plan.get("anchors", []):
                if anchor.get("id") == opening_id:
                    previously_used_openers.append(anchor.get("title"))
                    break
    
    logger.info(f"Starting Session Planner with Interview Type: {session_data.interview_type.value}")
    
    plan_result = await run_interview_planner(
        cv_text=resume.cv_text,
        job_description=session_data.job_description,
        match_report=match_report,
        interview_config={
            "interview_type": session_data.interview_type.value,
            "duration": duration_minutes,
            "focus_areas": session_data.focus_areas if hasattr(session_data, 'focus_areas') else []
        },
        previously_used_openers=previously_used_openers
    )
    
    if plan_result.get("error"):
        raise HTTPException(status_code=500, detail=plan_result["error"])
        
    planner_session_plan = plan_result.get("interview_plan")
    
    # 3.5 Run Agent 3 — Orchestrator (Hybrid Mode)
    from app.agents.orchestrator import run_orchestrator
    
    job_profile = {
        "calibrated_level": resume.analyzed_profile.get("experience_level", "junior") if resume.analyzed_profile else "junior",
        "priority_domains": session_data.focus_areas or []
    }
    
    logger.info("Starting Orchestrator for Hybrid Qdrant fetching")
    orchestrator_result = await run_orchestrator(
        planner_output=planner_session_plan,
        job_profile=job_profile
    )
    
    if orchestrator_result.get("error"):
        logger.error(f"Orchestrator failed, falling back to planner only: {orchestrator_result['error']}")
        session_plan = planner_session_plan
    else:
        session_plan = orchestrator_result.get("session_plan")
    
    # 4. Save Session
    new_session = Session(
        user_id=current_user.id,
        resume_id=resume.id,
        job_description=session_data.job_description,
        interview_type=session_data.interview_type,
        status=session_data.status,
        session_plan=session_plan
    )
    
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    
    return new_session

@router.get("/", response_model=list[SessionResponse])
async def list_sessions(
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve all sessions for the current user."""
    results = await db.execute(
        select(Session)
        .where(Session.user_id == current_user.id)
        .offset(skip).limit(limit)
    )
    return results.scalars().all()

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get a specific session with its plan."""
    session = await db.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.patch("/{session_id}/status", response_model=SessionResponse)
async def update_session_status(
    session_id: uuid.UUID,
    status_update: SessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update session status/time."""
    session = await db.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    update_data = status_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(session, field, value)
        
    await db.commit()
    await db.refresh(session)
    return session
