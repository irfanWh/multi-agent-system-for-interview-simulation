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
    previously_used_openers: list[str]
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

CRITICAL RULE based on Type ({interview_type}):
- If Type is "behavioral": Focus SOLELY on motivation, teamwork, leadership, conflict resolution, and decision-making. DO NOT ask about architecture, code, LLMs, APIs, or system design. Technical projects should only be used to ask behavioral questions (e.g., "Tell me about a challenging project you worked on").
- If Type is "technical": Focus on technical depth, architecture, coding, and system design.
- If Type is "mixed": Ensure a balanced mix of both behavioral and technical questions.

Types of anchors to find:
- Specific projects that relate to JD requirements
- Skills claimed in CV that JD requires — need to verify real depth
- Experience gaps between CV level and JD expectation
- Soft skills signals: leadership, communication, ownership

STEP 2 — Assign each anchor a position_in_flow and choose the opening anchor.

POSITION RULES:
- "opener": assign to 1-2 anchors that are:
    * A recent role or project the candidate clearly owns
    * A core skill that is definitely present in the CV AND required by JD
      (no ambiguity — this is not the place for gap probing)
    * Something that lets the candidate speak confidently right away
    * NOT the most complex or impressive item — save that for core
    * NOT a gap or missing skill — never open with a weakness
    * A good opener often sounds like: "Tell me about your work on X"
      where X is recent and clearly in their experience

- "core": assign to the majority of anchors:
    * Technical depth verification
    * Critical gap probing
    * The impressive projects (RAG pipeline, complex systems, etc.)
    * Experience validation
    * These go in the MIDDLE of the interview

- "closer": assign to 1-2 anchors that are:
    * Soft skills (leadership, communication, teamwork)
    * Motivation and career fit ("why this role")
    * Self-assessment ("what would you improve in your last project")
    * Always at the END — candidate should leave on a human note

ORDERING WITHIN EACH POSITION:
- Within "core" anchors: order from least threatening to most threatening.
  Start with strengths-to-validate before gap-probing.
  Build confidence before challenging.

OPENING ANCHOR SELECTION:
After assigning positions, choose opening_anchor_id:
- Must be an "opener" position anchor
- Prefer the most RECENT item in the CV over the most impressive
- If multiple openers exist, pick the one most directly tied to the
  core daily responsibilities in the JD (not the flashiest feature)

ANTI-PATTERNS — never do these:
- Opening with the candidate's most technically complex project
- Opening with a gap ("I notice you don't have experience in X...")
- Opening with a soft skill question before any technical discussion
- Assigning priority=1 automatically as the opener

IMPORTANT VARIABILITY GUARD:
The following anchor titles were used as openers in previous sessions for this candidate:
{previously_used_openers}

Do NOT select any of these as the opening_anchor_id.
Choose a different entry point to keep the experience fresh.
If all openers have been used, pick the least recently used one.

STEP 3 — For each anchor, define:
- opening_question: a specific question that references the actual CV content. 
  CRITICAL: Must respect the {interview_type}.
  TECHNICAL GOOD: "In your CV you mention building a RAG pipeline — can you walk me through the architecture you chose and why?"
  BEHAVIORAL GOOD: "Tell me about a challenging project you worked on and what your role was."
  BEHAVIORAL BAD: "How did you use LLMs in your project?"
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
                focus_areas=cfg.get("focus_areas", []),
                previously_used_openers=state.get("previously_used_openers", [])
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
    interview_config: dict,
    previously_used_openers: list[str] = None
) -> dict:
    """
    Public entry point: run the InterviewPlanner agent.
    Returns the final state dict containing 'interview_plan' or 'error'.
    """
    initial_state: PlannerState = {
        "cv_text": cv_text,
        "job_description": job_description or "",
        "match_report": match_report,
        "interview_config": interview_config,
        "previously_used_openers": previously_used_openers or []
    }
    result = await planner_app.ainvoke(initial_state)
    return result
