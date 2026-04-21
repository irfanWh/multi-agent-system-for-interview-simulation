"""
Profiles API — CV upload, profile CRUD.
"""
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import httpx
import re

from app.api.deps import get_db, get_current_user
from app.models.orm import CandidateProfile, User, ExperienceLevel
from app.models.schemas import (
    CandidateProfileCreate,
    CandidateProfileUpdate,
    CandidateProfileResponse,
)
from app.services.cv_parser import parse_cv

router = APIRouter()


@router.post("/upload-cv", response_model=CandidateProfileResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(
    file: UploadFile = File(...),
    target_role: str = Form("Software Engineer"),
    experience_level: ExperienceLevel = Form(ExperienceLevel.junior),
    job_description_text: Optional[str] = Form(None),
    job_description_url: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Upload a CV (PDF or DOCX).
    Extracts text, stores it in the candidate_profiles table.
    """
    # Validate file type
    if file.content_type not in (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are supported.",
        )

    file_bytes = await file.read()

    try:
        cv_text = parse_cv(file_bytes, file.filename or "file.pdf")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    job_description = None
    if job_description_url:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(job_description_url, timeout=10)
                resp.raise_for_status()
                # Basic strip HTML tags
                job_description = re.sub(r'<[^>]+>', ' ', resp.text)
                job_description = " ".join(job_description.split())
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch job description URL: {e}")
    elif job_description_text:
        job_description = job_description_text

    profile = CandidateProfile(
        user_id=current_user.id,
        cv_text=cv_text,
        target_role=target_role,
        experience_level=experience_level,
        job_description=job_description,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/{profile_id}", response_model=CandidateProfileResponse)
async def get_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Return a profile with skills_extracted."""
    profile = await db.scalar(
        select(CandidateProfile).where(
            CandidateProfile.id == profile_id,
            CandidateProfile.user_id == current_user.id,
        )
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/{profile_id}", response_model=CandidateProfileResponse)
async def update_profile(
    profile_id: uuid.UUID,
    update_data: CandidateProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update target_role and/or experience_level."""
    profile = await db.scalar(
        select(CandidateProfile).where(
            CandidateProfile.id == profile_id,
            CandidateProfile.user_id == current_user.id,
        )
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile


@router.post("/{profile_id}/analyze", response_model=CandidateProfileResponse)
async def analyze_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Trigger the Profile Analyzer agent (LangGraph).
    Analyses the CV text, extracts skills, detects gaps,
    calibrates level, and saves the result to skills_extracted.
    """
    profile = await db.scalar(
        select(CandidateProfile).where(
            CandidateProfile.id == profile_id,
            CandidateProfile.user_id == current_user.id,
        )
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if not profile.cv_text:
        raise HTTPException(
            status_code=400,
            detail="No CV text available. Upload a CV first.",
        )

    from app.agents.profile_analyzer import run_profile_analyzer

    result = await run_profile_analyzer(
        cv_text=profile.cv_text,
        target_role=profile.target_role,
        experience_level=profile.experience_level,
        job_description=profile.job_description,
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    # Save extracted profile to the DB
    profile.skills_extracted = result.get("extracted_profile", {})
    await db.commit()
    await db.refresh(profile)
    return profile


@router.post("/{profile_id}/match-analysis", response_model=CandidateProfileResponse)
async def analyze_match(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Trigger the Match Analyzer agent.
    Compares CV against Job Description and generates a MatchReport.
    """
    profile = await db.scalar(
        select(CandidateProfile).where(
            CandidateProfile.id == profile_id,
            CandidateProfile.user_id == current_user.id,
        )
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if not profile.cv_text or not profile.skills_extracted:
        raise HTTPException(status_code=400, detail="Profile must be analyzed first before generating a match report.")
        
    if not profile.job_description:
        raise HTTPException(status_code=400, detail="No job description provided for this profile.")

    from app.agents.match_analyzer import run_match_analyzer

    skills_list = profile.skills_extracted.get("detected_skills", [])
    level = profile.skills_extracted.get("calibrated_level", profile.experience_level.value)

    result = await run_match_analyzer(
        cv_text=profile.cv_text,
        job_description=profile.job_description,
        detected_skills=skills_list,
        calibrated_level=level
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    profile.match_report = result.get("match_report", {})
    await db.commit()
    await db.refresh(profile)
    return profile
