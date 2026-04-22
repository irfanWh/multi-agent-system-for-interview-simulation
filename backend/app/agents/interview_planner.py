import logging
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

from app.agents.profile_analyzer import _get_llm, _invoke_with_retries
from app.models.schemas import InterviewPlan

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Graph State
# ──────────────────────────────────────────────────────────────────────────────

class PlannerState(TypedDict, total=False):
    cv_text: str
    job_description: str
    match_report: Optional[dict]
    interview_config: dict
    interview_plan: Optional[dict]
    error: Optional[str]

# ──────────────────────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────────────────────

PLANNER_PROMPT = """\
You are a senior technical recruiter preparing for an interview.
You have read the candidate's CV and the job description carefully.

=== CANDIDATE CV ===
{cv_text}

=== JOB DESCRIPTION ===
{job_description}

=== MATCH REPORT ===
{match_report}

=== INTERVIEW CONFIG ===
Type: {interview_type}
Duration: {duration_minutes} minutes
Focus Areas requested by system: {focus_areas}

STEP 1 — Extract discussion anchors from the CV:
Look for elements in the CV that are directly relevant to what the JD needs.
For each anchor, note: what it is, why it matters for this role, and what
you want to discover about it (depth of experience? real ownership? results?)

Types of anchors to find:
- Specific projects that relate to JD requirements
- Skills claimed in CV that JD requires — need to verify real depth
- Experience gaps between CV level and JD expectation
- Soft skills signals: leadership, communication, ownership

STEP 2 — Order anchors by priority:
1. Critical gaps (skills/experience the JD requires that are weak in CV)
2. Key strengths to validate (important matches that need depth verification)
3. Interesting differentiators (things that make this candidate stand out)
4. Behavioral/soft skills (always last, unless role is primarily people-oriented)

STEP 3 — For each anchor, define:
- opening_question: a specific question that references the actual CV content
  GOOD: "In your CV you mention building a RAG pipeline at TechCorp — can you walk me through the architecture you chose and why?"
  BAD:  "Tell me about your experience with vector databases."
- what_to_listen_for: list of signals that indicate strong vs weak answer
- follow_up_directions: 2-3 directions to dig depending on the answer
- red_flags: answer patterns that suggest the claim is superficial
- time_allocation_minutes: how long to spend on this anchor

Pay very close attention to ensure total `time_allocation_minutes` across all anchors does NOT exceed {duration_minutes} minutes minus 5 minutes for intro/outro.

Produce the final output perfectly following the requested InterviewPlan schema.
"""

def generate_plan_node(state: PlannerState) -> PlannerState:
    try:
        llm = _get_llm()
        structured_llm = llm.with_structured_output(InterviewPlan)
        
        cfg = state.get("interview_config", {})
        
        result: InterviewPlan = _invoke_with_retries(
            structured_llm,
            PLANNER_PROMPT.format(
                cv_text=state.get("cv_text", ""),
                job_description=state.get("job_description", "No explicit job description provided. Assess based on target role."),
                match_report=state.get("match_report", {}),
                interview_type=cfg.get("interview_type", "mixed"),
                duration_minutes=cfg.get("duration", 30),
                focus_areas=cfg.get("focus_areas", [])
            )
        )
        return {"interview_plan": result.model_dump(), "error": None}
    except Exception as exc:
        logger.error("generate_plan_node failed: %s", exc)
        return {"error": f"Interview Planning failed: {exc}"}

# ──────────────────────────────────────────────────────────────────────────────
# Graph Assembly
# ──────────────────────────────────────────────────────────────────────────────

def build_planner_graph() -> StateGraph:
    graph = StateGraph(PlannerState)
    graph.add_node("generate_plan", generate_plan_node)
    graph.set_entry_point("generate_plan")
    graph.add_edge("generate_plan", END)
    return graph

planner_app = build_planner_graph().compile()

async def run_interview_planner(
    cv_text: str,
    job_description: str | None,
    match_report: dict | None,
    interview_config: dict
) -> dict:
    """
    Public entry point: run the InterviewPlanner agent.
    Returns the final state dict containing 'interview_plan' or 'error'.
    """
    initial_state: PlannerState = {
        "cv_text": cv_text,
        "job_description": job_description or "",
        "match_report": match_report,
        "interview_config": interview_config
    }
    result = await planner_app.ainvoke(initial_state)
    return result
