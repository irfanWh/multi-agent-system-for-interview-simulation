"""
Evaluator Agent — assesses each Exchange after the interview using:
  - The interviewer's react_scratchpad (internal reasoning)
  - The InterviewAnchor definition (what to listen for, red flags)
  - The anchor type (project/skill/gap/soft_skill) to apply correct rubric weights
"""
import logging
from typing import Optional
from pydantic import BaseModel, Field

from app.agents.profile_analyzer import _get_llm, _invoke_with_retries

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Rubric weight definitions by anchor type
# ──────────────────────────────────────────────────────────────────────────────

RUBRIC_WEIGHTS = {
    "project": {
        "depth": 0.40,
        "ownership": 0.30,
        "results": 0.30,
        "description": "Depth(40%), Ownership(30%), Results(30%)"
    },
    "skill": {
        "accuracy": 0.50,
        "depth": 0.30,
        "applied_context": 0.20,
        "description": "Accuracy(50%), Depth(30%), Applied Context(20%)"
    },
    "gap": {
        "self_awareness": 0.40,
        "mitigation_plan": 0.40,
        "honesty": 0.20,
        "description": "Self-Awareness(40%), Mitigation Plan(40%), Honesty(20%)"
    },
    "soft_skill": {
        "concrete_example": 0.50,
        "impact": 0.30,
        "reflection": 0.20,
        "description": "Concrete Example(50%), Impact(30%), Reflection(20%)"
    },
    "experience": {
        "depth": 0.40,
        "accuracy": 0.30,
        "applied_context": 0.30,
        "description": "Depth(40%), Accuracy(30%), Applied Context(30%)"
    }
}

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Output Schema
# ──────────────────────────────────────────────────────────────────────────────

class EvaluationResult(BaseModel):
    score: float = Field(description="Overall score from 0.0 to 10.0")
    dimension_scores: dict = Field(description="Breakdown by rubric dimension (0-10 each)")
    strengths: list[str] = Field(description="2-3 specific things the candidate did well")
    gaps: list[str] = Field(description="2-3 specific gaps or missed points")
    feedback: str = Field(description="One paragraph of honest, constructive written feedback")
    improvement_tips: list[str] = Field(description="3 actionable improvement suggestions")

# ──────────────────────────────────────────────────────────────────────────────
# Prompt
# ──────────────────────────────────────────────────────────────────────────────

EVALUATOR_PROMPT = """\
You are an expert technical recruiter evaluating a candidate's interview response.

=== ANCHOR CONTEXT ===
Title: {anchor_title}
Type: {anchor_type}
Rubric Weights: {rubric_description}

What the interviewer was looking for:
{what_to_listen_for}

Red flags to detect:
{red_flags}

Why this anchor matters for the role:
{jd_relevance}

=== INTERVIEWER'S INTERNAL REASONING ===
(This is the interviewer's live assessment — use it to calibrate your evaluation)
{react_scratchpad}

Interviewer's confidence level during this exchange: {interviewer_confidence}/5

=== EXCHANGE ===
Question asked:
{question}

Candidate's answer:
{candidate_answer}

=== EVALUATION TASK ===
Apply the rubric weights for anchor type "{anchor_type}":
{rubric_description}

Score each rubric dimension from 0 to 10.
Compute the overall weighted score (0.0 to 10.0).

Be very specific — quote the candidate's words when assessing.
Do not penalize for nervousness or communication style.
Do penalize for:
  - Factual inaccuracies
  - Claims not backed by evidence
  - Vague answers that avoid the question
  - Triggered red flags

Provide output in the exact requested schema.
"""

# ──────────────────────────────────────────────────────────────────────────────
# Public Entry Point
# ──────────────────────────────────────────────────────────────────────────────

async def evaluate_exchange(
    question: str,
    candidate_answer: str,
    anchor: Optional[dict] = None,
    react_scratchpad: Optional[str] = None,
    interviewer_confidence: int = 3
) -> dict:
    """
    Evaluate a single exchange.
    Returns the full EvaluationResult as a dict, or an error dict.
    """
    try:
        # Defaults if no anchor (backwards compatibility)
        anchor = anchor or {}
        anchor_type = anchor.get("type", "skill")
        rubric = RUBRIC_WEIGHTS.get(anchor_type, RUBRIC_WEIGHTS["skill"])
        
        llm = _get_llm()
        structured_llm = llm.with_structured_output(EvaluationResult)
        
        result: EvaluationResult = _invoke_with_retries(
            structured_llm,
            EVALUATOR_PROMPT.format(
                anchor_title=anchor.get("title", "General"),
                anchor_type=anchor_type,
                rubric_description=rubric.get("description", ""),
                what_to_listen_for="\n- ".join(anchor.get("what_to_listen_for", ["Strong, specific, evidence-based answer"])),
                red_flags="\n- ".join(anchor.get("red_flags", ["Vague generalities without examples"])),
                jd_relevance=anchor.get("jd_relevance", "Core technical competency needed for this role"),
                react_scratchpad=react_scratchpad or "Not available",
                interviewer_confidence=interviewer_confidence,
                question=question,
                candidate_answer=candidate_answer or "(No answer provided)"
            )
        )
        
        return result.model_dump()
        
    except Exception as exc:
        logger.error("evaluate_exchange failed: %s", exc)
        return {"error": str(exc)}
