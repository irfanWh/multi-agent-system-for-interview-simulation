"""
Agent 5 — Report Generator (LangGraph StateGraph)

After an interview session completes, this agent:
  1. Aggregates all exchange evaluations into domain-level scores
  2. Uses LLM to write a personalised feedback narrative
  3. Uses LLM to produce an actionable improvement plan
  4. Assembles a complete ReportData dict for PDF generation
"""
import logging
from typing import TypedDict, Optional, List, Dict, Any

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from app.agents.profile_analyzer import _get_llm, _invoke_with_retries
from app.services.strengths_service import aggregate_competency_breakdown

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic output schemas for LLM structured output
# ──────────────────────────────────────────────────────────────────────────────

class NarrativeFeedback(BaseModel):
    session_summary: str = Field(description="300-400 word personalised feedback narrative")
    strengths: List[str] = Field(description="3-5 key strengths demonstrated during the interview")
    areas_for_improvement: List[str] = Field(description="3-5 areas where the candidate should improve")

class ActionStep(BaseModel):
    step: str = Field(description="Specific, actionable improvement step")
    resources: str = Field(description="Recommended resources (courses, books, projects)")
    timeframe: str = Field(description="Realistic timeframe to achieve this (e.g. '2 weeks', '1 month')")

class ActionPlan(BaseModel):
    steps: List[ActionStep] = Field(description="5 specific, actionable improvement steps")

# ──────────────────────────────────────────────────────────────────────────────
# Graph State
# ──────────────────────────────────────────────────────────────────────────────

class ReportGeneratorState(TypedDict, total=False):
    session_id: str
    exchanges: List[dict]          # [{question, candidate_answer, evaluation, anchor_type, domain}]
    session_plan: dict
    competency_breakdown: dict     # {domain: {score, nb_questions, feedback}}
    global_score: float
    exchange_annotations: List[dict]
    narrative: Optional[dict]      # {session_summary, strengths, areas_for_improvement}
    action_plan: Optional[List[dict]]
    report_data: Optional[dict]
    error: Optional[str]

# ──────────────────────────────────────────────────────────────────────────────
# Node 1 — Aggregate Scores
# ──────────────────────────────────────────────────────────────────────────────

def aggregate_scores_node(state: ReportGeneratorState) -> ReportGeneratorState:
    """Compute averages by domain, identify patterns, build annotations."""
    exchanges = state.get("exchanges", [])

    exchange_annotations = []
    total_global = 0.0
    total_count = 0
    
    for ex in exchanges:
        ev = ex.get("evaluation") or {}
        
        # Compute per-exchange average score
        scores = []
        for key in ("score_accuracy", "score_depth", "score_clarity", "score_star"):
            val = ev.get(key)
            if val is not None and val > 0:
                scores.append(val)
        avg = sum(scores) / len(scores) if scores else 0.0
        if scores:
            total_global += avg
            total_count += 1
        
        # Build annotation
        tips = ev.get("improvement_tips", {})
        exchange_annotations.append({
            "question": ex.get("question", ""),
            "answer_excerpt": (ex.get("candidate_answer", "") or "")[:200],
            "score": round(avg, 1),
            "key_feedback": ev.get("feedback", "No evaluation available"),
            "strengths": tips.get("strengths", []) if isinstance(tips, dict) else [],
            "tips": tips.get("tips", []) if isinstance(tips, dict) else [],
        })
    
    competency_breakdown = aggregate_competency_breakdown(exchanges)
    
    global_score = round(total_global / max(total_count, 1), 1)
    
    return {
        "competency_breakdown": competency_breakdown,
        "global_score": global_score,
        "exchange_annotations": exchange_annotations,
    }

# ──────────────────────────────────────────────────────────────────────────────
# Node 2 — Generate Narrative
# ──────────────────────────────────────────────────────────────────────────────

NARRATIVE_PROMPT = """\
You are a senior interview coach writing a personalised feedback report for a candidate.

=== SESSION DATA ===
Global Score: {global_score}/10
Domains evaluated: {domains}
Number of questions: {num_questions}

=== COMPETENCY BREAKDOWN ===
{competency_text}

=== SAMPLE EXCHANGE ANNOTATIONS ===
{annotations_text}

=== TASK ===
Write a personalised feedback narrative (300-400 words) that:
1. Opens with the overall impression and global score context
2. Highlights specific strengths with concrete examples from the interview
3. Addresses areas for improvement constructively
4. Provides encouragement and a forward-looking perspective

Also extract 3-5 key strengths and 3-5 areas for improvement as separate lists.
Be specific — reference actual question topics and answer quality.
Tone: professional, constructive, encouraging.
"""

def generate_narrative_node(state: ReportGeneratorState) -> ReportGeneratorState:
    """LLM writes personalised feedback narrative."""
    try:
        breakdown = state.get("competency_breakdown", {})
        annotations = state.get("exchange_annotations", [])
        
        # Format competency text
        comp_lines = []
        for domain, data in breakdown.items():
            comp_lines.append(f"- {domain}: {data['score']}/10 ({data['nb_questions']} questions) — {data['feedback']}")
        competency_text = "\n".join(comp_lines) or "No competency data available."
        
        # Format annotations (first 5)
        ann_lines = []
        for ann in annotations[:5]:
            ann_lines.append(f"Q: {ann['question'][:100]}\n  Score: {ann['score']}/10 — {ann['key_feedback'][:150]}")
        annotations_text = "\n".join(ann_lines) or "No annotations available."
        
        llm = _get_llm()
        structured_llm = llm.with_structured_output(NarrativeFeedback)
        
        result: NarrativeFeedback = _invoke_with_retries(
            structured_llm,
            NARRATIVE_PROMPT.format(
                global_score=state.get("global_score", 0),
                domains=", ".join(breakdown.keys()),
                num_questions=len(annotations),
                competency_text=competency_text,
                annotations_text=annotations_text,
            )
        )
        
        return {"narrative": result.model_dump()}
    except Exception as exc:
        logger.error("generate_narrative_node failed: %s", exc)
        return {"narrative": {
            "session_summary": f"Interview completed with a global score of {state.get('global_score', 0)}/10.",
            "strengths": ["Unable to generate detailed strengths."],
            "areas_for_improvement": ["Unable to generate detailed improvement areas."],
        }}

# ──────────────────────────────────────────────────────────────────────────────
# Node 3 — Generate Action Plan
# ──────────────────────────────────────────────────────────────────────────────

ACTION_PLAN_PROMPT = """\
You are a senior career coach creating a specific improvement plan for a candidate.

=== INTERVIEW RESULTS ===
Global Score: {global_score}/10
Strengths: {strengths}
Areas for Improvement: {areas}

=== COMPETENCY BREAKDOWN ===
{competency_text}

=== TASK ===
Create exactly 5 specific, actionable improvement steps. For each step:
1. Be very specific about what to study/practice (not generic advice)
2. Recommend concrete resources (specific course names, book titles, project ideas)
3. Give a realistic timeframe

Prioritise the weakest domains first.
Focus on practical, achievable steps.
"""

def generate_action_plan_node(state: ReportGeneratorState) -> ReportGeneratorState:
    """LLM produces 5 specific, actionable improvement steps."""
    try:
        narrative = state.get("narrative", {})
        breakdown = state.get("competency_breakdown", {})
        
        comp_lines = []
        for domain, data in breakdown.items():
            comp_lines.append(f"- {domain}: {data['score']}/10")
        competency_text = "\n".join(comp_lines) or "No data."
        
        llm = _get_llm()
        structured_llm = llm.with_structured_output(ActionPlan)
        
        result: ActionPlan = _invoke_with_retries(
            structured_llm,
            ACTION_PLAN_PROMPT.format(
                global_score=state.get("global_score", 0),
                strengths=", ".join(narrative.get("strengths", [])),
                areas=", ".join(narrative.get("areas_for_improvement", [])),
                competency_text=competency_text,
            )
        )
        
        return {"action_plan": [s.model_dump() for s in result.steps]}
    except Exception as exc:
        logger.error("generate_action_plan_node failed: %s", exc)
        return {"action_plan": [{
            "step": "Review weak domains identified in the interview",
            "resources": "Online courses and documentation",
            "timeframe": "2-4 weeks"
        }]}

# ──────────────────────────────────────────────────────────────────────────────
# Node 4 — Build Report Data
# ──────────────────────────────────────────────────────────────────────────────

def build_report_data_node(state: ReportGeneratorState) -> ReportGeneratorState:
    """Assemble complete report dict."""
    narrative = state.get("narrative", {})
    
    report_data = {
        "session_id": state.get("session_id", ""),
        "session_summary": narrative.get("session_summary", ""),
        "global_score": state.get("global_score", 0.0),
        "competency_breakdown": state.get("competency_breakdown", {}),
        "strengths": narrative.get("strengths", []),
        "areas_for_improvement": narrative.get("areas_for_improvement", []),
        "action_plan": state.get("action_plan", []),
        "exchange_annotations": state.get("exchange_annotations", []),
    }
    
    return {"report_data": report_data}

# ──────────────────────────────────────────────────────────────────────────────
# Graph Assembly
# ──────────────────────────────────────────────────────────────────────────────

def build_report_generator_graph() -> StateGraph:
    graph = StateGraph(ReportGeneratorState)
    
    graph.add_node("aggregate_scores", aggregate_scores_node)
    graph.add_node("generate_narrative", generate_narrative_node)
    graph.add_node("generate_action_plan", generate_action_plan_node)
    graph.add_node("build_report_data", build_report_data_node)
    
    graph.set_entry_point("aggregate_scores")
    graph.add_edge("aggregate_scores", "generate_narrative")
    graph.add_edge("generate_narrative", "generate_action_plan")
    graph.add_edge("generate_action_plan", "build_report_data")
    graph.add_edge("build_report_data", END)
    
    return graph

report_generator_app = build_report_generator_graph().compile()

async def run_report_generator(session_id: str, exchanges: list, session_plan: dict = None) -> dict:
    """Run the report generator agent. Returns the final state dict."""
    initial_state = {
        "session_id": session_id,
        "exchanges": exchanges,
        "session_plan": session_plan or {},
    }
    config = {"recursion_limit": 20}
    result = await report_generator_app.ainvoke(initial_state, config=config)
    return result
