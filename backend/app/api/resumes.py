import logging
import re
from typing import List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.api.deps import get_current_user, get_db
from app.models.orm import User, Resume, Session as InterviewSession
from app.services.resume_service import ResumeService

router = APIRouter(prefix="/resumes", tags=["Resumes"])
logger = logging.getLogger(__name__)

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a new resume or return the existing one if exact file already exists.
    """
    if not file.filename.endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only PDF, DOCX, and TXT are allowed."
        )

    file_bytes = await file.read()
    if len(file_bytes) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large")

    resume, was_duplicate = await ResumeService.upload_resume(
        user_id=str(current_user.id),
        file_bytes=file_bytes,
        filename=file.filename,
        db=db
    )

    return {
        "resume_id": str(resume.id),
        "filename": resume.filename,
        "is_analyzed": resume.is_analyzed,
        "was_duplicate": was_duplicate
    }

@router.get("")
async def list_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Return list of user's resumes with usage counts.
    """
    # Subquery to count sessions per resume
    subq = (
        select(InterviewSession.resume_id, func.count(InterviewSession.id).label("sessions_count"))
        .group_by(InterviewSession.resume_id)
        .subquery()
    )

    query = (
        select(Resume, func.coalesce(subq.c.sessions_count, 0).label("sessions_count"))
        .outerjoin(subq, Resume.id == subq.c.resume_id)
        .where(
            Resume.user_id == current_user.id,
            Resume.is_recruiter_candidate == False
        )
        .order_by(Resume.created_at.desc())
    )
    
    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "id": str(r[0].id),
            "filename": r[0].filename,
            "created_at": r[0].created_at,
            "is_analyzed": r[0].is_analyzed,
            "sessions_count": r[1]
        }
        for r in rows
    ]

@router.get("/{resume_id}")
async def get_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return full resume including analyzed_profile if available."""
    resume = await db.get(Resume, resume_id)
    if not resume or str(resume.user_id) != str(current_user.id) or resume.is_recruiter_candidate:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    return {
        "id": str(resume.id),
        "filename": resume.filename,
        "is_analyzed": resume.is_analyzed,
        "analyzed_profile": resume.analyzed_profile,
        "created_at": resume.created_at
    }

@router.get("/{resume_id}/status")
async def get_resume_status(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return just the analysis status for polling."""
    resume = await db.get(Resume, resume_id)
    if not resume or str(resume.user_id) != str(current_user.id) or resume.is_recruiter_candidate:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    return {"is_analyzed": resume.is_analyzed}

@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a resume from DB and storage.
    If the resume has been used in sessions, sessions_count is returned so frontend can warn the user.
    The delete proceeds regardless (sessions will have resume_id set to NULL via cascade).
    """
    resume = await db.get(Resume, resume_id)
    if not resume or str(resume.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Resume not found")

    if resume.is_recruiter_candidate:
        raise HTTPException(
            status_code=400,
            detail="Recruiter candidate resumes cannot be deleted from the personal resume dashboard."
        )

    # Count sessions that used this resume
    sessions_count_res = await db.execute(
        select(func.count(InterviewSession.id)).where(InterviewSession.resume_id == resume_id)
    )
    sessions_count = sessions_count_res.scalar()

    # Delete from MinIO storage
    try:
        from app.services.storage import StorageService
        storage = StorageService()
        object_name = f"resumes/{current_user.id}/{resume.file_hash}_{resume.filename}"
        await storage.delete_file("model-artifacts", object_name)
    except Exception as e:
        logger.warning(f"Could not delete file from storage (proceeding anyway): {e}")

    await db.delete(resume)
    await db.commit()
    return {"status": "deleted", "sessions_affected": sessions_count}

class MatchRequest(BaseModel):
    job_description: str

def validate_job_description(text: str) -> str | None:
    if not text or not text.strip():
        return "Job description is empty."
        
    clean_text = text.strip()
        
    word_count = len([w for w in clean_text.split() if w])
    
    if word_count < 50 and len(clean_text) < 300:
        return "Please enter a valid job description with responsibilities, required skills, and experience level."
        
    meaningful_keywords = [
        'role', 'responsibilities', 'skills', 'requirements', 'experience', 
        'qualifications', 'technologies', 'tasks', 'company', 'developer',
        'engineer', 'manager', 'lead', 'senior', 'junior', 'degree',
        'knowledge', 'proficiency', 'working', 'ability',
        'mission', 'profil recherché', 'compétences', 'expérience',
        'responsabilités', "offre d'emploi", 'profil', 'requis'
    ]
    
    text_lower = clean_text.lower()
    has_meaningful = any(kw in text_lower for kw in meaningful_keywords)
    
    if not has_meaningful:
        return "Please enter a valid job description with responsibilities, required skills, and experience level."
        
    # Repeated characters check
    if re.search(r'(.)\1{10,}', clean_text):
        return "Please enter a valid job description with responsibilities, required skills, and experience level. (Invalid text format)"
        
    return None

@router.post("/{resume_id}/match-analysis")
async def match_analysis(
    resume_id: str,
    request: MatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return match analysis for a (resume, JD) pair."""
    resume = await db.get(Resume, resume_id)
    if not resume or str(resume.user_id) != str(current_user.id) or resume.is_recruiter_candidate:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    if not resume.is_analyzed:
        raise HTTPException(status_code=400, detail="Resume is still being analyzed")
        
    validation_error = validate_job_description(request.job_description)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)
        
    try:
        report, was_cached = await ResumeService.get_match_analysis(
            resume_id=resume_id,
            job_description=request.job_description,
            db=db
        )
        return {
            "match_report": report,
            "was_cached": was_cached
        }
    except Exception as e:
        logger.error(f"Error generating match report: {e}")
        raise HTTPException(status_code=500, detail="Match analysis failed")
