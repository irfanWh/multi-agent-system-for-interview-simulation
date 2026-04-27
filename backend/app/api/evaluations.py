from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
import uuid

from app.api.deps import get_db
from app.models.orm import Evaluation, Exchange, Session

router = APIRouter()

@router.get("/sessions/{session_id}/evaluations")
async def get_session_evaluations(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Return all evaluations for a given session."""
    session_obj = await db.scalar(
        select(Session)
        .options(selectinload(Session.exchanges).selectinload(Exchange.evaluation))
        .where(Session.id == session_id)
    )
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
        
    evaluations = []
    for ex in session_obj.exchanges:
        if ex.evaluation:
            evaluations.append({
                "exchange_id": str(ex.id),
                "turn_number": ex.turn_number,
                "question": ex.question,
                "candidate_answer": ex.candidate_answer,
                "evaluation": {
                    "id": str(ex.evaluation.id),
                    "score_accuracy": ex.evaluation.score_accuracy,
                    "score_depth": ex.evaluation.score_depth,
                    "score_clarity": ex.evaluation.score_clarity,
                    "score_star": ex.evaluation.score_star,
                    "feedback": ex.evaluation.feedback,
                    "improvement_tips": ex.evaluation.improvement_tips
                }
            })
            
    return evaluations

@router.get("/exchanges/{exchange_id}/evaluation")
async def get_exchange_evaluation(exchange_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Return evaluation for a specific exchange."""
    evaluation = await db.scalar(
        select(Evaluation)
        .where(Evaluation.exchange_id == exchange_id)
    )
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found for this exchange")
        
    return {
        "id": str(evaluation.id),
        "exchange_id": str(evaluation.exchange_id),
        "score_accuracy": evaluation.score_accuracy,
        "score_depth": evaluation.score_depth,
        "score_clarity": evaluation.score_clarity,
        "score_star": evaluation.score_star,
        "feedback": evaluation.feedback,
        "improvement_tips": evaluation.improvement_tips
    }
