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
    score: float = Field(description="0-10 scale candidate score")
    candidate_score: float = Field(default=0.0, description="Alias: 0-10 scale")
    required_score: float = Field(default=5.0, description="0-10 required level")
    matched: int
    total: int

class ExperienceMatch(BaseModel):
    score: float
    candidate_years: int
    required_years: int
    verdict: str

class SenioritySignal(BaseModel):
    signal: str = Field(description="e.g. 'Technical depth', 'Ownership', 'Leadership', 'Impact'")
    score: float = Field(description="0-10")

class KeywordAlignment(BaseModel):
    keyword: str
    jd_frequency: int = Field(description="How many times the keyword appears in the JD")
    found_in_cv: bool

class CvVsJdInsight(BaseModel):
    type: str = Field(description="'gap', 'strength', or 'warning'")
    title: str
    body: str

class InterviewFocusArea(BaseModel):
    domain: str
    reason: str
    probability: str = Field(description="'high', 'medium', or 'low'")
    tip: str

class SoftSkillsMatch(BaseModel):
    score: float
    found: List[str]
    missing: List[str]

class MatchReport(BaseModel):
    """Structured output representing the Match Analysis."""
    global_match_score: float = Field(description="Score from 0.0 to 100.0")
    readiness_level: str = Field(description="'strong_match', 'good_match', 'partial_match', or 'weak_match'")
    recommendation: str = Field(description="2-sentence human-readable verdict")
    skills_matched: List[MatchedSkill]
    skills_missing: List[MissingSkill]
    skills_exceeded: List[str] = Field(default_factory=list, description="Skills where candidate has MORE than required")
    domain_scores: List[DomainScore]
    experience_match: ExperienceMatch
    seniority_signals: List[SenioritySignal] = Field(default_factory=list, description="Seniority calibration signals")
    keyword_alignment: List[KeywordAlignment] = Field(default_factory=list, description="JD keyword presence in CV")
    cv_vs_jd_insights: List[CvVsJdInsight] = Field(default_factory=list, description="Narrative gap/strength/warning insights")
    soft_skills_found: List[str] = Field(default_factory=list)
    soft_skills_missing: List[str] = Field(default_factory=list)
    soft_skills_tip: str = Field(default="", description="Tip for improving soft skills presentation")
    soft_skills_match: SoftSkillsMatch = Field(default=None, description="Legacy soft skills match object")
    interview_focus_areas: List[InterviewFocusArea] = Field(default_factory=list, description="Top areas the interview should focus on")

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
You are an expert HR Analyst. Analyze the match between the candidate's CV and the Job Description.
Produce a comprehensive structured match report.

Target Level detected by system: {calibrated_level}
Candidate Skills detected: {detected_skills}

=== CANDIDATE CV ===
{cv_text}

=== JOB DESCRIPTION ===
{job_description}

Think step-by-step (Chain-of-Thought):
1. Extract ALL required skills, years of experience, soft skills, and key terms from the JD.
2. Cross-reference each requirement with the CV text and detected candidate skills.
3. For each skill, determine the candidate's level (junior/mid/senior/expert) vs required level.
4. Identify skills that are matched, missing, or exceeded.
5. For missing skills, classify as "critical" or "nice_to_have" and estimate learning time in weeks.
6. Group skills into domains (e.g. "Frontend", "Backend", "DevOps", "Data", "Soft Skills").
   For each domain give a candidate_score (0-10) and required_score (0-10).
7. Evaluate experience: candidate_years vs required_years, produce a verdict.
8. Assess seniority signals: "Technical depth", "Ownership", "Leadership", "Impact" — score each 0-10.
9. Extract the top 15-20 keywords from the JD. For each, count its frequency in the JD
   and check if it appears in the CV (found_in_cv: true/false).
10. Produce 3-5 narrative cv_vs_jd_insights. Each has type ("gap", "strength", or "warning"),
    a short title, and a 1-2 sentence body.
11. List soft skills found in the CV and soft skills expected by JD but missing. Provide a tip.
12. Pick 3-4 interview_focus_areas where the candidate is weakest. For each, give:
    domain, reason, probability ("high"/"medium"/"low"), and a preparation tip.
13. Compute global_match_score (0-100), readiness_level, and a 2-sentence recommendation.

Produce the final output perfectly following the requested MatchReport schema.
Ensure ALL fields are populated — do not leave any list empty if you can infer data.
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
