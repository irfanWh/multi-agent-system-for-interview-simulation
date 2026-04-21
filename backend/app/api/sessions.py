import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import get_db, get_current_user
from app.models.orm import Session, User, CandidateProfile
from app.models.schemas import SessionCreate, SessionResponse, SessionUpdate

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
    # 1. Fetch related profile
    if not session_data.profile_id:
        raise HTTPException(status_code=400, detail="profile_id is required")
        
    profile = await db.scalar(
        select(CandidateProfile).where(
            CandidateProfile.id == session_data.profile_id,
            CandidateProfile.user_id == current_user.id
        )
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
        
    # 2. Run Profile Analyzer if skills_extracted is empty
    if not profile.skills_extracted:
        if not profile.cv_text:
            raise HTTPException(status_code=400, detail="Profile has no parsed CV text")
            
        from app.agents.profile_analyzer import run_profile_analyzer
        result = await run_profile_analyzer(
            cv_text=profile.cv_text,
            target_role=profile.target_role,
            experience_level=profile.experience_level.value,
            job_description=profile.job_description,
        )
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
            
        profile.skills_extracted = result.get("extracted_profile", {})
        await db.commit()
        await db.refresh(profile)

    # 3. Run Agent 2 — Orchestrator
    from app.agents.orchestrator import run_orchestrator
    
    orch_result = await run_orchestrator(
        job_profile=profile.skills_extracted,
        interview_type=session_data.interview_type.value,
        duration_minutes=duration_minutes,
        job_description=profile.job_description,
        focus_areas=session_data.focus_areas,
    )
    
    if orch_result.get("error"):
        raise HTTPException(status_code=500, detail=orch_result["error"])
        
    session_plan = orch_result.get("session_plan")
    
    # 4. Save Session
    new_session = Session(
        user_id=current_user.id,
        profile_id=profile.id,
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
