import os
import asyncio
import logging
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def _build_sync_db_url() -> str:
    """Convert the asyncpg URL to a sync psycopg URL for use inside Celery workers."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://interviewai_user:change_me_postgres_password@localhost:5432/interviewai_db"
    )
    # Normalise driver prefix to plain psycopg (sync)
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
            break
    return url


async def _analyze_resume_async(resume_id: str) -> None:
    """Run the profile‑analyzer agent and persist results.

    A *fresh* async engine is created per‑task so that there is no shared
    connection‑pool state across forked Celery worker processes.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.models.orm import Resume
    from app.agents.profile_analyzer import run_profile_analyzer

    # Build asyncpg URL from whatever scheme is in the environment
    raw_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://interviewai_user:change_me@localhost:5432/interviewai_db"
    )
    # Normalise to asyncpg driver
    for sync_prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql://"):
        if raw_url.startswith(sync_prefix):
            raw_url = "postgresql+asyncpg://" + raw_url[len(sync_prefix):]
            break
    # @@ in URL means the password itself contains @.
    # asyncpg needs it percent-encoded: @@ → %40@
    raw_url = raw_url.replace("@@", "%40@", 1)

    # ── NEW engine per task – avoids forked‑pool issues ──────────────────────
    engine = create_async_engine(raw_url, echo=False, future=True, pool_size=1, max_overflow=0)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            resume = await db.get(Resume, resume_id)
            if not resume:
                logger.error(f"Resume {resume_id} not found in DB")
                return

            if resume.is_analyzed:
                logger.info(f"Resume {resume_id} already analyzed — skipping")
                return

            cv_text = resume.cv_text or ""
            if not cv_text.strip():
                logger.warning(f"Resume {resume_id} has no extracted text; marking as analyzed with empty profile")
                resume.analyzed_profile = {}
                resume.is_analyzed = True
                await db.commit()
                return

            result_state = await run_profile_analyzer(
                cv_text=cv_text,
                target_role=None,
                experience_level=None,
            )

            if result_state.get("error"):
                raise ValueError(result_state["error"])

            resume.analyzed_profile = result_state.get("extracted_profile", {})
            resume.is_analyzed = True
            await db.commit()
            logger.info(f"Resume {resume_id} analyzed successfully")

    except Exception as exc:
        logger.error(f"Error analyzing resume {resume_id}: {exc}", exc_info=True)
        raise
    finally:
        await engine.dispose()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_resume_task(self, resume_id: str):
    """Celery entry‑point: runs the async analysis in a brand‑new event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_analyze_resume_async(resume_id))
    except Exception as exc:
        logger.error(f"Task failed for resume {resume_id}: {exc}")
        raise self.retry(exc=exc)
    finally:
        loop.close()
        asyncio.set_event_loop(None)
