import os
import asyncio
import logging
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

async def _evaluate_exchange_async(exchange_id: str, anchor: dict, interviewer_confidence: int) -> None:
    """Run the evaluator agent and persist results.
    
    A *fresh* async engine is created per‑task so that there is no shared
    connection‑pool state across forked Celery worker processes.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.models.orm import Exchange, Evaluation
    from app.agents.evaluator import evaluate_exchange

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
    raw_url = raw_url.replace("@@", "%40@", 1)

    engine = create_async_engine(raw_url, echo=False, future=True, pool_size=1, max_overflow=0)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            exchange = await db.get(Exchange, exchange_id)
            if not exchange:
                logger.error(f"Exchange {exchange_id} not found in DB")
                return

            eval_result = await evaluate_exchange(
                question=exchange.question,
                candidate_answer=exchange.candidate_answer,
                anchor=anchor,
                react_scratchpad=exchange.react_scratchpad,
                interviewer_confidence=interviewer_confidence
            )

            if not eval_result.get("error"):
                evaluation = Evaluation(
                    exchange_id=exchange.id,
                    score_accuracy=eval_result.get("score_accuracy"),
                    score_depth=eval_result.get("score_depth"),
                    score_clarity=eval_result.get("score_clarity"),
                    score_star=eval_result.get("score_star"),
                    feedback=eval_result.get("feedback", ""),
                    improvement_tips={
                        "tips": eval_result.get("improvement_tips", []),
                        "strengths": eval_result.get("strengths", []),
                        "global_score": eval_result.get("global_score")
                    }
                )
                db.add(evaluation)
                await db.commit()
                logger.info(f"Exchange {exchange_id} evaluated successfully")
            else:
                logger.error(f"Evaluation returned error: {eval_result.get('error')}")

    except Exception as exc:
        logger.error(f"Error evaluating exchange {exchange_id}: {exc}", exc_info=True)
        raise
    finally:
        await engine.dispose()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def evaluate_exchange_task(self, exchange_id: str, anchor: dict, interviewer_confidence: int = 3):
    """Celery entry‑point: runs the async evaluation in a brand‑new event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_evaluate_exchange_async(exchange_id, anchor, interviewer_confidence))
    except Exception as exc:
        logger.error(f"Task failed for exchange {exchange_id}: {exc}")
        raise self.retry(exc=exc)
    finally:
        loop.close()
        asyncio.set_event_loop(None)
