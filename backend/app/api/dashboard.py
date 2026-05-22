import logging
from typing import Any
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.api.deps import get_db, get_current_user
from app.models.orm import Session, User, Resume, Report, SessionStatus
from app.models.schemas import DashboardStatsResponse, ScoreEvolution, StrengthsProfile

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
            Session.status == SessionStatus.active
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
        
    # 4. Strengths Profile (average competency scores across all reports)
    reports_query = await db.execute(
        select(Report.competency_breakdown)
        .join(Session, Report.session_id == Session.id)
        .where(
            Session.user_id == user_id,
            Report.competency_breakdown.isnot(None)
        )
    )
    
    category_scores = {}
    category_counts = {}
    
    for row in reports_query.all():
        breakdown = row[0]
        if not breakdown or not isinstance(breakdown, dict):
            continue
            
        for category, data in breakdown.items():
            if isinstance(data, dict) and 'score' in data:
                score = data['score']
                category_scores[category] = category_scores.get(category, 0) + score
                category_counts[category] = category_counts.get(category, 0) + 1
    
    strengths_profile = []
    # If no data, we could return empty array, but we might want standard categories with 0
    # The requirement is: "If some score data is missing, return null or empty arrays, not fake values."
    for category, total_score in category_scores.items():
        count = category_counts[category]
        if count > 0:
            avg = total_score / count
            # Clean up category names (e.g. "system_design" -> "System Design")
            clean_category = category.replace("_", " ").title()
            strengths_profile.append(StrengthsProfile(category=clean_category, score=round(avg, 1)))
            
    # Sort by score descending so radar chart looks nicer
    strengths_profile.sort(key=lambda x: x.score, reverse=True)
    # Take top 6 categories to not overcrowd the radar chart
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
