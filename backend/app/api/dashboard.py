import logging
from typing import Any
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.api.deps import get_db, get_current_user
from app.models.orm import Session, User, Resume, Report, SessionStatus, Exchange, Evaluation
from app.models.schemas import DashboardStatsResponse, ScoreEvolution, StrengthsProfile
from app.services.strengths_service import (
    category_scores_for_exchange,
    clean_category_name,
    level_for_score,
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get aggregated dashboard statistics for the current user.
    """
    user_id = current_user.id
    
    # 1. Basic counts
    total_interviews_query = await db.execute(
        select(func.count(Session.id)).where(Session.user_id == user_id)
    )
    total_interviews = total_interviews_query.scalar() or 0
    
    completed_interviews_query = await db.execute(
        select(func.count(Session.id)).where(
            Session.user_id == user_id, 
            Session.status == SessionStatus.completed
        )
    )
    completed_interviews = completed_interviews_query.scalar() or 0
    
    active_interviews_query = await db.execute(
        select(func.count(Session.id)).where(
            Session.user_id == user_id, 
            Session.status.in_([SessionStatus.active, SessionStatus.in_progress])
        )
    )
    active_interviews = active_interviews_query.scalar() or 0
    
    active_resumes_query = await db.execute(
        select(func.count(Resume.id)).where(Resume.user_id == user_id)
    )
    active_resumes = active_resumes_query.scalar() or 0
    
    # 2. Aggregations on Report global score
    # We join Session with Report to make sure we only look at reports for this user
    stats_query = await db.execute(
        select(
            func.avg(Report.global_score),
            func.max(Report.global_score)
        )
        .join(Session, Report.session_id == Session.id)
        .where(Session.user_id == user_id)
    )
    stats_row = stats_query.first()
    avg_score = round(stats_row[0], 1) if stats_row and stats_row[0] is not None else None
    best_score = round(stats_row[1], 1) if stats_row and stats_row[1] is not None else None
    
    # 3. Score Evolution (last 5 completed sessions with a report)
    # We order by started_at ascending so chart goes from oldest to newest
    evolution_query = await db.execute(
        select(Session.started_at, Report.global_score)
        .join(Report, Session.id == Report.session_id)
        .where(
            Session.user_id == user_id,
            Session.status == SessionStatus.completed,
            Report.global_score.isnot(None)
        )
        .order_by(Session.started_at.desc())
        .limit(10)
    )
    
    evolution_rows = evolution_query.all()
    # Reverse to get chronological order (oldest first)
    evolution_rows.reverse()
    
    score_evolution = []
    for i, row in enumerate(evolution_rows):
        dt = row[0]
        date_str = dt.strftime("%b %d") if dt else f"Session {i+1}"
        score = round(row[1], 1)
        score_evolution.append(ScoreEvolution(date=date_str, score=score))
        
    # 4. Strengths Profile
    # Prefer structured report categories. For older reports that only contain
    # "General", derive categories from persisted evaluations and session anchors.
    reports_query = await db.execute(
        select(Session.id, Report.competency_breakdown)
        .join(Report, Session.id == Report.session_id)
        .where(
            Session.user_id == user_id,
            Session.status == SessionStatus.completed,
            Report.competency_breakdown.isnot(None)
        )
    )

    category_totals: dict[str, float] = {}
    category_counts: dict[str, int] = {}
    category_sessions: dict[str, set[str]] = {}
    category_feedback: dict[str, list[str]] = {}
    sessions_with_structured_reports: set[str] = set()

    def add_strength(category: str, score: float, session_id: Any, feedback: str | None = None) -> None:
        clean_category = clean_category_name(category)
        category_totals[clean_category] = category_totals.get(clean_category, 0.0) + float(score)
        category_counts[clean_category] = category_counts.get(clean_category, 0) + 1
        category_sessions.setdefault(clean_category, set()).add(str(session_id))
        if feedback:
            category_feedback.setdefault(clean_category, []).append(feedback)

    for row in reports_query.all():
        session_id = row[0]
        breakdown = row[1]
        if not breakdown or not isinstance(breakdown, dict):
            continue

        has_structured_categories = False
        for category, data in breakdown.items():
            if category.strip().lower() == "general":
                continue
            if isinstance(data, dict) and data.get("score") is not None:
                try:
                    score = float(data["score"])
                except (TypeError, ValueError):
                    continue
                add_strength(
                    category=category,
                    score=max(0.0, min(10.0, score)),
                    session_id=session_id,
                    feedback=data.get("feedback") or data.get("insights"),
                )
                has_structured_categories = True

        if has_structured_categories:
            sessions_with_structured_reports.add(str(session_id))

    evaluations_query = await db.execute(
        select(
            Session.id,
            Session.interview_type,
            Session.session_plan,
            Exchange.turn_number,
            Evaluation.score_accuracy,
            Evaluation.score_depth,
            Evaluation.score_clarity,
            Evaluation.score_star,
            Evaluation.feedback,
        )
        .join(Exchange, Exchange.session_id == Session.id)
        .join(Evaluation, Evaluation.exchange_id == Exchange.id)
        .where(
            Session.user_id == user_id,
            Session.status == SessionStatus.completed,
        )
    )

    for row in evaluations_query.all():
        session_id = str(row[0])
        if session_id in sessions_with_structured_reports:
            continue

        session_plan = row[2] or {}
        anchors = session_plan.get("anchors", []) if isinstance(session_plan, dict) else []
        anchor_type = "skill"
        anchor_idx = max((row[3] or 1) - 1, 0)
        if anchors and anchor_idx < len(anchors):
            anchor_type = anchors[anchor_idx].get("type", "skill")

        exchange_data = {
            "anchor_type": anchor_type,
            "interview_type": getattr(row[1], "value", row[1]),
            "evaluation": {
                "score_accuracy": row[4],
                "score_depth": row[5],
                "score_clarity": row[6],
                "score_star": row[7],
                "feedback": row[8],
            },
        }

        for category, score in category_scores_for_exchange(exchange_data).items():
            add_strength(category, score, session_id, row[8])

    strengths_profile = []
    for category, total_score in category_totals.items():
        count = category_counts[category]
        if count > 0:
            avg = total_score / count
            feedback_items = category_feedback.get(category, [])
            strengths_profile.append(StrengthsProfile(
                category=category,
                average_score=round(avg, 1),
                percentage=round(avg * 10, 1),
                level=level_for_score(avg),
                interviews_used=len(category_sessions.get(category, set())),
                feedback_summary=feedback_items[0] if feedback_items else None,
            ))

    strengths_profile.sort(key=lambda x: x.average_score, reverse=True)
    strengths_profile = strengths_profile[:6]
    
    return DashboardStatsResponse(
        total_interviews=total_interviews,
        completed_interviews=completed_interviews,
        active_interviews=active_interviews,
        active_resumes=active_resumes,
        average_score=avg_score,
        best_score=best_score,
        score_evolution=score_evolution,
        strengths_profile=strengths_profile
    )
