"""
Reports API — endpoints for interview report generation and retrieval.

GET  /sessions/{id}/report          — return report data + pdf_url
POST /sessions/{id}/generate-report — trigger Celery task (if not already done)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
import json

from app.api.deps import get_db, get_current_user
from app.models.orm import Report, Session, SessionStatus, User

router = APIRouter()


@router.get("/sessions/{session_id}/report")
async def get_session_report(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the report data and PDF URL for a session."""
    session = await db.scalar(
        select(Session).where(Session.id == session_id, Session.user_id == current_user.id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    report = await db.scalar(
        select(Report).where(Report.session_id == session_id)
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found for this session. Generate it first.")

    # Parse action_plan if stored as JSON string
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


@router.post("/sessions/{session_id}/generate-report")
async def trigger_report_generation(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger report generation as a Celery background task."""
    # Check session exists
    session_obj = await db.scalar(
        select(Session).where(Session.id == session_id, Session.user_id == current_user.id)
    )
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check if report already exists with a PDF URL
    existing_report = await db.scalar(
        select(Report).where(Report.session_id == session_id)
    )
    if existing_report and existing_report.pdf_url:
        return {
            "status": "already_generated",
            "message": "Report already exists for this session.",
            "pdf_url": existing_report.pdf_url,
        }

    # Trigger the Celery task
    from app.tasks.report import generate_report_task
    task = generate_report_task.delay(str(session_id))

    return {
        "status": "generating",
        "message": "Report generation started. This may take 1-2 minutes.",
        "task_id": task.id,
    }
