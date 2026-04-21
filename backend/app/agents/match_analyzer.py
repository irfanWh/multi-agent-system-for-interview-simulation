"""
Agent — Match Analyzer (LangGraph)

Analyzes the match between a candidate's extracted profile (CV) and the provided Job Description.
Generates a structured MatchReport for the frontend dashboard.
"""
import os
import logging
from typing import List, Optional, TypedDict

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from app.agents.profile_analyzer import _get_llm, _invoke_with_retries

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Output Schemas
# ──────────────────────────────────────────────────────────────────────────────

class MatchedSkill(BaseModel):
    skill: str
    level_in_cv: str
    level_required: str

class MissingSkill(BaseModel):
    skill: str
    importance: str = Field(description="'critical' or 'nice_to_have'")
    learn_time_weeks: int

class DomainScore(BaseModel):
    domain: str
    score: float
    matched: int
    total: int

class ExperienceMatch(BaseModel):
    score: float
    candidate_years: int
    required_years: int
    verdict: str

class SoftSkillsMatch(BaseModel):
    score: float
    found: List[str]
    missing: List[str]

class MatchReport(BaseModel):
    """Structured output representing the Match Analysis."""
    global_match_score: float = Field(description="Score from 0.0 to 100.0")
    skills_matched: List[MatchedSkill]
    skills_missing: List[MissingSkill]
    skills_exceeded: List[str] = Field(description="Skills where candidate has MORE than required")
    domain_scores: List[DomainScore]
    experience_match: ExperienceMatch
    soft_skills_match: SoftSkillsMatch
    interview_focus_areas: List[str] = Field(description="Top 3 topics the interview should focus on given gaps")
    recommendation: str = Field(description="2-sentence human-readable verdict")
    readiness_level: str = Field(description="'strong_match', 'good_match', 'partial_match', or 'weak_match'")

# ──────────────────────────────────────────────────────────────────────────────
# Graph State
# ──────────────────────────────────────────────────────────────────────────────

class MatchAnalyzerState(TypedDict, total=False):
    cv_text: str
    job_description: str
    detected_skills: List[str]
    calibrated_level: str
    match_report: Optional[dict]
    error: Optional[str]

# ──────────────────────────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────────────────────────

MATCH_ANALYZER_PROMPT = """\
You are an expert HR Analyst. Check the match between the candidate's CV and the Job Description.

Target Level detected by system: {calibrated_level}
Candidate Skills detected: {detected_skills}

=== CANDIDATE CV ===
{cv_text}

=== JOB DESCRIPTION ===
{job_description}

Think step-by-step (Chain-of-Thought):
1. Extract required skills, required years of experience, and soft skills from the Job Description.
2. Cross-reference these requirements with the CV text and the detected candidate skills.
3. Determine which skills are matched, missing, or exceeded.
4. For missing skills, guess if it's "critical" or "nice_to_have" and estimate learning time in weeks.
5. Grade the candidate overall (0 to 100) and grade specific domains.
6. Provide an experience verdict and soft skills analysis.
7. Finally, pick 3 interview_focus_areas where the candidate is weak, so the interviewer can test them.

Produce the final output perfectly following the requested MatchReport schema.
"""

def analyze_match_node(state: MatchAnalyzerState) -> MatchAnalyzerState:
    try:
        llm = _get_llm()
        structured_llm = llm.with_structured_output(MatchReport)

        result: MatchReport = _invoke_with_retries(
            structured_llm,
            MATCH_ANALYZER_PROMPT.format(
                calibrated_level=state.get("calibrated_level", "unknown"),
                detected_skills=", ".join(state.get("detected_skills", [])),
                cv_text=state.get("cv_text", ""),
                job_description=state.get("job_description", "")
            )
        )
        return {"match_report": result.model_dump(), "error": None}
    except Exception as exc:
        logger.error("analyze_match_node failed: %s", exc)
        return {"error": f"Match Analysis failed: {exc}"}

# ──────────────────────────────────────────────────────────────────────────────
# Graph Assembly
# ──────────────────────────────────────────────────────────────────────────────

def build_match_analyzer_graph() -> StateGraph:
    graph = StateGraph(MatchAnalyzerState)
    graph.add_node("analyze_match", analyze_match_node)
    graph.set_entry_point("analyze_match")
    graph.add_edge("analyze_match", END)
    return graph

match_analyzer_app = build_match_analyzer_graph().compile()

async def run_match_analyzer(
    cv_text: str,
    job_description: str,
    detected_skills: List[str],
    calibrated_level: str
) -> dict:
    initial_state: MatchAnalyzerState = {
        "cv_text": cv_text,
        "job_description": job_description,
        "detected_skills": detected_skills,
        "calibrated_level": calibrated_level
    }
    result = await match_analyzer_app.ainvoke(initial_state)
    return result
