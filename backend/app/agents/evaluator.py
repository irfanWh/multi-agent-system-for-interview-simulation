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
from app.services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Rubric weight definitions by anchor type
# ──────────────────────────────────────────────────────────────────────────────

RUBRIC_WEIGHTS = {
    "project": {
        "depth": 0.40,
        "ownership": 0.30,
        "accuracy": 0.30,
        "description": "Depth(40%), Ownership(30%), Accuracy/Results(30%)"
    },
    "skill": {
        "accuracy": 0.50,
        "depth": 0.30,
        "clarity": 0.20,
        "description": "Accuracy(50%), Depth(30%), Clarity(20%)"
    },
    "gap": {
        "accuracy": 0.40,
        "depth": 0.40,
        "clarity": 0.20,
        "description": "Self-Awareness/Accuracy(40%), Mitigation/Depth(40%), Honesty/Clarity(20%)"
    },
    "soft_skill": {
        "clarity": 0.50,
        "depth": 0.30,
        "star": 0.20,
        "description": "Concrete Example/Clarity(50%), Impact/Depth(30%), STAR Structure(20%)"
    },
    "experience": {
        "depth": 0.40,
        "accuracy": 0.30,
        "clarity": 0.30,
        "description": "Depth(40%), Accuracy(30%), Clarity(30%)"
    }
}

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Output Schema
# ──────────────────────────────────────────────────────────────────────────────

class EvaluationResult(BaseModel):
    chain_of_thought: str = Field(description="LLM reasoning before scoring (not shown to user)")
    score_accuracy: float = Field(description="0-10: factual/technical correctness")
    score_depth: float = Field(description="0-10: depth of analysis")
    score_clarity: float = Field(description="0-10: clarity and structure of communication")
    score_star: float = Field(description="0-10: STAR structure (0 if not behavioral/soft_skill)")
    global_score: float = Field(description="weighted average based on anchor type")
    feedback: str = Field(description="2-3 sentences shown to candidate immediately")
    improvement_tips: list[str] = Field(description="2-3 actionable tips for next time")
    strengths: list[str] = Field(description="what was done well")

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

Reference Answer (for calibration, do not penalize if wording differs, only if semantic meaning is wrong):
{reference_answer}

Think step-by-step (chain_of_thought):
1. What would an expert answer look like for this? What key points are expected?
2. Compare the candidate's answer to the ideal.
3. Determine the scores (0-10) for accuracy, depth, clarity, and star structure.
4. Calculate the global_score based on the rubric weights.
5. Provide specific strengths, feedback, and improvement tips.

Be very specific — quote the candidate's words when assessing.
Do not penalize for nervousness.
Do penalize for:
  - Factual inaccuracies
  - Claims not backed by evidence
  - Vague answers that avoid the question
  - Triggered red flags

Produce the final output perfectly following the EvaluationResult schema.
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
                what_to_listen_for="\\n- ".join(anchor.get("what_to_listen_for", ["Strong, specific, evidence-based answer"])),
                red_flags="\\n- ".join(anchor.get("red_flags", ["Vague generalities without examples"])),
                jd_relevance=anchor.get("jd_relevance", "Core technical competency needed for this role"),
                react_scratchpad=react_scratchpad or "Not available",
                interviewer_confidence=interviewer_confidence,
                question=question,
                candidate_answer=candidate_answer or "(No answer provided)",
                reference_answer=anchor.get("reference_answer", "Not provided")
            )
        )
        
        # Calculate Semantic Similarity Score
        qdrant = QdrantService.get_instance()
        reference_answer = anchor.get("reference_answer", "")
        similarity_score = 0.0
        
        if reference_answer and candidate_answer:
            similarity = await qdrant.compute_similarity(candidate_answer, reference_answer)
            # Map cosine similarity (0 to 1) to a 0-10 scale.
            # Usually, good answers are > 0.7. Let's scale it so 0.4=0, 0.85=10.
            normalized_sim = max(0.0, min(1.0, (similarity - 0.4) / 0.45))
            similarity_score = normalized_sim * 10.0
            logger.info(f"Similarity: {similarity:.3f} -> Score: {similarity_score:.1f}/10")
            
            # Hybrid Scoring (60% LLM / 40% Similarity for Accuracy)
            original_accuracy = result.score_accuracy
            result.score_accuracy = round((original_accuracy * 0.6) + (similarity_score * 0.4), 1)
            
            # Recalculate global score
            rubric = RUBRIC_WEIGHTS.get(anchor_type, RUBRIC_WEIGHTS["skill"])
            
            # Safe calculation assuming missing keys are 0
            new_global = 0.0
            if "accuracy" in rubric: new_global += result.score_accuracy * rubric["accuracy"]
            if "depth" in rubric: new_global += result.score_depth * rubric["depth"]
            if "clarity" in rubric: new_global += result.score_clarity * rubric["clarity"]
            if "ownership" in rubric: new_global += result.score_clarity * rubric["ownership"] # approximating ownership with clarity if needed
            if "star" in rubric: new_global += result.score_star * rubric["star"]
            
            # Simple fallback if the weights don't sum to exactly 1
            if new_global > 0:
                result.global_score = round(new_global, 1)

        return result.model_dump()
        
    except Exception as exc:
        logger.error("evaluate_exchange failed: %s", exc)
        return {"error": str(exc)}
