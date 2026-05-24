import hashlib
import json
import logging
from typing import List, Tuple, Optional
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.orm import Resume, MatchCache
# from app.agents.profile_analyzer import profile_analyzer_agent
from app.agents.match_analyzer import run_match_analyzer
from app.tasks.resume import analyze_resume_task
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

class ResumeService:
    @staticmethod
    async def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
        if filename.endswith(".pdf"):
            import io
            import pypdf
            pdf_file = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
        elif filename.endswith(".docx"):
            import io
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join([para.text for para in doc.paragraphs])
            return text
        return file_bytes.decode('utf-8', errors='ignore')

    @classmethod
    async def upload_resume(
        cls,
        user_id: str,
        file_bytes: bytes,
        filename: str,
        db: AsyncSession,
        is_recruiter_candidate: bool = False,
    ) -> Tuple[Resume, bool]:
        """
        Upload a new resume. If exact same file was already uploaded
        by this user, return the existing resume without re-processing.
        """
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Check for duplicate
        result = await db.execute(
            select(Resume).where(
                Resume.user_id == user_id,
                Resume.file_hash == file_hash,
                Resume.is_recruiter_candidate == is_recruiter_candidate,
            )
        )
        existing_resume = result.scalar_one_or_none()

        if existing_resume:
            return existing_resume, True

        # New resume
        cv_text = await cls.extract_text_from_file(file_bytes, filename)
        
        # Save file to storage (optional, but good practice)
        storage = StorageService()
        await storage.upload_file("model-artifacts", f"resumes/{user_id}/{file_hash}_{filename}", file_bytes)

        resume = Resume(
            user_id=user_id,
            filename=filename,
            cv_text=cv_text,
            file_hash=file_hash,
            is_analyzed=False,
            is_recruiter_candidate=is_recruiter_candidate,
        )
        db.add(resume)
        await db.commit()
        await db.refresh(resume)

        # Trigger analysis as background task
        analyze_resume_task.delay(str(resume.id))

        return resume, False

    @staticmethod
    async def get_user_resumes(user_id: str, db: AsyncSession) -> List[Resume]:
        """Return all resumes for a user, ordered by most recently created."""
        result = await db.execute(
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_match_analysis(
        resume_id: str,
        job_description: str,
        db: AsyncSession
    ) -> Tuple[dict, bool]:
        """
        Return match analysis for a (resume, JD) pair.
        Uses cache if available — no LLM call if already computed.
        Schema version is included in the hash so stale cache entries
        from older schema versions are automatically bypassed.
        """
        MATCH_SCHEMA_VERSION = "v2"  # bump when MatchReport fields change
        jd_hash = hashlib.sha256(
            f"{MATCH_SCHEMA_VERSION}:{job_description}".encode('utf-8')
        ).hexdigest()

        # Check cache first
        result = await db.execute(
            select(MatchCache).where(
                MatchCache.resume_id == resume_id,
                MatchCache.jd_hash == jd_hash
            )
        )
        hit = result.scalar_one_or_none()

        if hit:
            return hit.match_report, True

        # Cache miss — fetch resume, run MatchAnalyzer agent
        resume = await db.get(Resume, resume_id)
        if not resume:
            raise ValueError("Resume not found")
        if not resume.is_analyzed:
            raise ValueError("Resume not yet analyzed — wait for analysis to complete")

        # Create schemas for match analyzer input
        detected_skills = resume.analyzed_profile.get("detected_skills", []) if resume.analyzed_profile else []
        calibrated_level = resume.analyzed_profile.get("calibrated_level", "unknown") if resume.analyzed_profile else "unknown"
        
        result_state = await run_match_analyzer(
            cv_text=resume.cv_text,
            job_description=job_description,
            detected_skills=detected_skills,
            calibrated_level=calibrated_level
        )

        if result_state.get("error"):
            raise ValueError(result_state["error"])
            
        match_report_dict = result_state.get("match_report", {})

        # Store in cache
        cache_entry = MatchCache(
            resume_id=resume_id,
            jd_hash=jd_hash,
            jd_text=job_description[:500],
            match_report=match_report_dict
        )
        db.add(cache_entry)
        await db.commit()

        return match_report_dict, False
