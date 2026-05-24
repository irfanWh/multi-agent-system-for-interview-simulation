"""
Celery task — generate_report_task

Orchestrates:
  1. Fetch session + exchanges + evaluations from DB
  2. Run Report Generator agent (LangGraph)
  3. Generate PDF bytes (ReportLab)
  4. Upload to MinIO bucket interview-reports
  5. Generate presigned URL (7 days expiry)
  6. Save Report to DB + update session status to "completed"
"""
import os
import asyncio
import logging
import json
from datetime import timedelta

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def _build_async_db_url() -> str:
    """Build an asyncpg URL from the environment DATABASE_URL."""
    raw_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://interviewai_user:change_me@localhost:5432/interviewai_db"
    )
    for sync_prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql://"):
        if raw_url.startswith(sync_prefix):
            raw_url = "postgresql+asyncpg://" + raw_url[len(sync_prefix):]
            break
    raw_url = raw_url.replace("@@", "%40@", 1)
    return raw_url


def _get_minio_client():
    """Create a MinIO client from env vars."""
    from minio import Minio
    endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "irfan123@")
    
    return Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
    )


async def _generate_report_async(session_id: str) -> None:
    """Core async logic for report generation."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.future import select
    from sqlalchemy.orm import selectinload
    from app.models.orm import Session, Exchange, Evaluation, Report, SessionStatus, RecruiterInterview
    from app.agents.report_generator import run_report_generator
    from app.services.pdf_service import generate_report_pdf

    raw_url = _build_async_db_url()
    engine = create_async_engine(raw_url, echo=False, future=True, pool_size=1, max_overflow=0)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            # 1. Fetch session + exchanges + evaluations
            session_obj = await db.scalar(
                select(Session)
                .options(
                    selectinload(Session.exchanges).selectinload(Exchange.evaluation)
                )
                .where(Session.id == session_id)
            )
            if not session_obj:
                logger.error(f"Session {session_id} not found")
                return

            # Check if report already exists
            existing_report = await db.scalar(
                select(Report).where(Report.session_id == session_id)
            )
            if existing_report and existing_report.pdf_url:
                logger.info(f"Report already exists for session {session_id}")
                return

            # Build exchange dicts for the agent
            exchange_dicts = []
            session_plan = session_obj.session_plan or {}
            anchors = session_plan.get("anchors", [])
            
            for ex in session_obj.exchanges:
                ev_dict = {}
                if ex.evaluation:
                    ev_dict = {
                        "score_accuracy": ex.evaluation.score_accuracy,
                        "score_depth": ex.evaluation.score_depth,
                        "score_clarity": ex.evaluation.score_clarity,
                        "score_star": ex.evaluation.score_star,
                        "feedback": ex.evaluation.feedback,
                        "improvement_tips": ex.evaluation.improvement_tips,
                    }
                
                # Try to find domain from anchors
                domain = "General"
                anchor_type = "skill"
                for anchor in anchors:
                    title = anchor.get("title", "")
                    if title and title.lower() in (ex.question or "").lower():
                        domain = anchor.get("domain", "General")
                        anchor_type = anchor.get("type", "skill")
                        break
                
                # Fallback: derive domain from the exchange order vs anchor order
                if domain == "General" and anchors:
                    anchor_idx = min(ex.turn_number - 1, len(anchors) - 1)
                    if anchor_idx >= 0:
                        domain = anchors[anchor_idx].get("domain", "General")
                        anchor_type = anchors[anchor_idx].get("type", "skill")
                
                exchange_dicts.append({
                    "question": ex.question,
                    "candidate_answer": ex.candidate_answer,
                    "evaluation": ev_dict,
                    "domain": domain,
                    "anchor_type": anchor_type,
                    "interview_type": getattr(session_obj.interview_type, "value", session_obj.interview_type),
                })

            logger.info(f"Running report generator for session {session_id} with {len(exchange_dicts)} exchanges")

            # 2. Run the report generator agent
            result_state = await run_report_generator(
                session_id=str(session_id),
                exchanges=exchange_dicts,
                session_plan=session_plan,
            )

            report_data = result_state.get("report_data", {})
            if not report_data:
                logger.error(f"Report generator returned empty report_data for session {session_id}")
                return

            # 3. Generate PDF
            pdf_bytes = generate_report_pdf(report_data, str(session_id))

            # 4. Upload to MinIO
            import io
            minio_client = _get_minio_client()
            bucket = os.environ.get("MINIO_BUCKET_REPORTS", "interview-reports")
            object_name = f"{session_id}/report.pdf"

            minio_client.put_object(
                bucket_name=bucket,
                object_name=object_name,
                data=io.BytesIO(pdf_bytes),
                length=len(pdf_bytes),
                content_type="application/pdf",
            )
            logger.info(f"PDF uploaded to MinIO: {bucket}/{object_name}")

            # 5. Generate presigned URL (7 days)
            presigned_url = minio_client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=timedelta(days=7),
            )
            logger.info(f"Presigned URL generated for session {session_id}")

            # 6. Save Report to DB
            if existing_report:
                existing_report.global_score = report_data.get("global_score")
                existing_report.competency_breakdown = report_data.get("competency_breakdown")
                existing_report.action_plan = json.dumps(report_data.get("action_plan", []))
                existing_report.pdf_url = presigned_url
            else:
                report = Report(
                    session_id=session_obj.id,
                    global_score=report_data.get("global_score"),
                    competency_breakdown=report_data.get("competency_breakdown"),
                    action_plan=json.dumps(report_data.get("action_plan", [])),
                    pdf_url=presigned_url,
                )
                db.add(report)

            # Update session status to completed
            session_obj.status = SessionStatus.completed
            recruiter_interview = await db.scalar(
                select(RecruiterInterview).where(RecruiterInterview.session_id == session_obj.id)
            )
            if recruiter_interview:
                recruiter_interview.status = SessionStatus.completed
            await db.commit()
            logger.info(f"Report saved for session {session_id} — status set to completed")

    except Exception as exc:
        logger.error(f"Error generating report for session {session_id}: {exc}", exc_info=True)
        raise
    finally:
        await engine.dispose()


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def generate_report_task(self, session_id: str):
    """Celery entry-point: generate the full interview report."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_generate_report_async(session_id))
    except Exception as exc:
        logger.error(f"Report task failed for session {session_id}: {exc}")
        raise self.retry(exc=exc)
    finally:
        loop.close()
        asyncio.set_event_loop(None)
