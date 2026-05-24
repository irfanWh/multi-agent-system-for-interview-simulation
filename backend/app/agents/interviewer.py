import logging
from typing import TypedDict, Any, List, Optional
import uuid
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END
from sqlalchemy.future import select
from app.agents.profile_analyzer import _get_llm, _invoke_with_retries
from app.models.orm import Exchange, Session

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# State Schema
# ──────────────────────────────────────────────────────────────────────────────

class InterviewerState(TypedDict, total=False):
    session_id: str
    interview_plan: dict
    current_anchor_id: str
    current_anchor_turns: int
    exchanges: List[dict]
    last_candidate_answer: str
    react_scratchpad: str
    next_action: str
    follow_up_question: str # Could also be probe gap or acknowledge move.
    anchor_assessment: str
    completed_anchors: List[str]
    session_complete: bool
    time_elapsed_minutes: float
    
    # Internal variables mapping
    send_fn: Any
    recv_fn: Any
    db: Any

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas for LLM outputs
# ──────────────────────────────────────────────────────────────────────────────

class ReActDecision(BaseModel):
    observe: str = Field(description="What did the candidate actually say? What are the key points?")
    assess: str = Field(description="How does this answer compare to what_to_listen_for? Any red flags?")
    confidence: int = Field(description="Confidence level about their competence on this anchor (1-5)")
    action: str = Field(description="'follow_up' | 'probe_gap' | 'acknowledge_move' | 'close'")
    reasoning: str = Field(description="Why I chose this action")
    message_to_candidate: str = Field(description="The exact text to send to the candidate")

# ──────────────────────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────────────────────

REACT_REASONING_PROMPT = """\
You are conducting a technical interview. Think step by step before deciding
what to do next. This is your internal reasoning — the candidate cannot see it.

CURRENT ANCHOR: {anchor_title}
ANCHOR TYPE: {anchor_type}
OPENING QUESTION ASKED: {opening_question}
WHAT TO LISTEN FOR: {what_to_listen_for}
FOLLOW-UP DIRECTIONS AVAILABLE: {follow_up_directions}
RED FLAGS TO WATCH: {red_flags}

TURNS SPENT ON THIS ANCHOR: {current_anchor_turns} / max {time_allocation_minutes} min
ANCHORS REMAINING: {remaining_anchors}

CONVERSATION SO FAR ON THIS ANCHOR:
{anchor_conversation_history}

CANDIDATE'S LATEST ANSWER:
{last_candidate_answer}

Now reason:

OBSERVE: What did the candidate actually say? What are the key points?
Was anything vague, impressive, concerning, or surprising?

ASSESS: How does this answer compare to what_to_listen_for?
Did they trigger any red_flags? Did they demonstrate depth or breadth?
What is my current confidence level about their competence on this anchor? (scale 1-5, explain why)

DECIDE — choose ONE action:
  A) "follow_up" — there is something in their answer worth digging into.
     Specify EXACTLY what and why. Generate the follow-up question.
     A follow-up MUST reference something they just said.

  B) "probe_gap" — their answer revealed a gap or a red flag.
     Do NOT signal that you detected a gap. Ask a natural question
     that lets them show more depth if they have it.

  C) "acknowledge_move" — you have enough signal on this anchor
     (either strong positive or confirmed gap). Acknowledge their answer
     naturally and state that we are moving to the next topic. 
     CRITICAL: Do NOT ask any questions in your message_to_candidate for this action! 
     The system will automatically append the next question for you.

  D) "close" — all anchors covered OR time is up. Deliver closing_statement.

OUTPUT: Return perfectly structured output parsing to the requested schema.
message_to_candidate is the ONLY thing the candidate sees.
"""

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_current_anchor(state: InterviewerState) -> Optional[dict]:
    plan = state.get("interview_plan", {})
    anchors = plan.get("anchors", [])
    current_id = state.get("current_anchor_id")
    for a in anchors:
        if a["id"] == current_id:
            return a
    return None

def get_next_anchor(state: InterviewerState) -> Optional[dict]:
    plan = state.get("interview_plan", {})
    anchors = plan.get("anchors", [])
    completed = state.get("completed_anchors", [])
    
    remaining = [a for a in anchors if a["id"] not in completed]
    if not remaining:
        return None
        
    position_order = {"opener": 0, "core": 1, "closer": 2}
    remaining.sort(key=lambda a: (
        position_order.get(a.get("position_in_flow", "core"), 1),
        a.get("priority", 99)
    ))
    return remaining[0]

# ──────────────────────────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────────────────────────

async def open_interview_node(state: InterviewerState) -> InterviewerState:
    """Deliver opening_statement and ask first anchor's opening_question."""
    plan = state.get("interview_plan", {})
    opening_anchor_id = plan.get("opening_anchor_id")
    
    # Try to find the explicitly chosen opening anchor
    first_anchor = None
    if opening_anchor_id:
        for a in plan.get("anchors", []):
            if a["id"] == opening_anchor_id:
                first_anchor = a
                break
                
    # Fallback if not found or not provided
    if not first_anchor:
        first_anchor = get_next_anchor(state)
        
    if not first_anchor:
        return {"session_complete": True}

    db = state["db"]
    session_id = state["session_id"]
    
    # Query interview_type
    session_obj = await db.scalar(select(Session).where(Session.id == session_id))
    interview_type = session_obj.interview_type.value if session_obj else "mixed"
    
    candidate_name = plan.get("candidate_name", "")
    generic_greeting = f"Hello {candidate_name}, welcome to the interview!" if candidate_name else "Hello, welcome to the interview!"
    
    if interview_type == "behavioral":
        # Force deterministic behavioral opener
        first_q = "To start, can you tell me about yourself, your background, and what you are currently doing?"
        msg = f"{generic_greeting}\n\n{first_q}"
    else:
        first_q = first_anchor.get("opening_question", "")
        msg = f"{generic_greeting}\n\n{first_q}"
    
    send_fn = state["send_fn"]
    
    await send_fn({
        "type": "question",
        "text": msg,
        "anchor_title": first_anchor.get("title")
    })
    
    return {
        "current_anchor_id": first_anchor["id"],
        "current_anchor_turns": 1,
        "last_candidate_answer": "",
        "follow_up_question": msg # record the question we asked
    }

async def wait_answer_node(state: InterviewerState) -> InterviewerState:
    """Wait for candidate's WebSocket reply."""
    recv_fn = state["recv_fn"]
    msg = await recv_fn()
    if msg.get("type") == "disconnect":
         return {"session_complete": True}
         
    return {
        "last_candidate_answer": msg.get("text", "").strip()
    }

def wait_answer_condition(state: InterviewerState) -> str:
    if state.get("session_complete"):
        return "end"
    return "react_reasoning"

async def react_reasoning_node(state: InterviewerState) -> InterviewerState:
    """LLM reasons based on ReAct core instructions."""
    anchor = get_current_anchor(state)
    plan = state.get("interview_plan", {})
    
    if not anchor:
         return {"next_action": "close"}
         
    completed = state.get("completed_anchors", [])
    all_anchors = plan.get("anchors", [])
    remaining_count = len(all_anchors) - len(completed) - 1
    
    # gather exchange history on current anchor
    history = []
    for ex in state.get("exchanges", []):
         history.append(f"Interviewer: {ex['question']}\nCandidate: {ex['answer']}")
    history_str = "\n".join(history[-3:]) # Last few turns
    
    llm = _get_llm()
    structured_llm = llm.with_structured_output(ReActDecision)
    
    result: ReActDecision = _invoke_with_retries(
        structured_llm,
        REACT_REASONING_PROMPT.format(
            anchor_title=anchor.get("title", ""),
            anchor_type=anchor.get("type", ""),
            opening_question=anchor.get("opening_question", ""),
            what_to_listen_for=", ".join(anchor.get("what_to_listen_for", [])),
            follow_up_directions=", ".join(anchor.get("follow_up_directions", [])),
            red_flags=", ".join(anchor.get("red_flags", [])),
            current_anchor_turns=state.get("current_anchor_turns", 1),
            time_allocation_minutes=anchor.get("time_allocation_minutes", 5),
            remaining_anchors=max(0, remaining_count),
            anchor_conversation_history=history_str,
            last_candidate_answer=state.get("last_candidate_answer", "")
        )
    )
    
    
    scratchpad = (
        f"OBSERVE: {result.observe}\n"
        f"ASSESS: {result.assess}\n"
        f"CONFIDENCE: {result.confidence}\n"
        f"DECISION REASONING: {result.reasoning}"
    )

    # QUESTION GUARD FOR BEHAVIORAL MODE
    db = state["db"]
    session_id = state["session_id"]
    session_obj = await db.scalar(select(Session).where(Session.id == session_id))
    interview_type = session_obj.interview_type.value if session_obj else "mixed"
    
    follow_up_question = result.message_to_candidate
    
    if interview_type == "behavioral" and result.action in ["follow_up", "probe_gap"]:
        blocked_terms = [
            "llm", "langgraph", "api", "architecture", "backend", "frontend", "database", 
            "model", "pipeline", "fastapi", "react", "python", "docker", "cloud", 
            "implementation", "system design", "algorithm", "framework", "code", "infrastructure"
        ]
        lower_q = follow_up_question.lower()
        has_blocked_term = any(term in lower_q for term in blocked_terms)
        
        if has_blocked_term:
            logger.warning(f"Question Guard Intercepted Behavioral Question: {follow_up_question}")
            # Rewrite it to be behavioral
            follow_up_question = "That's interesting. What was the most challenging part of that for you personally, and how did you collaborate with others to overcome it?"
            logger.info(f"Question Guard Rewrote to: {follow_up_question}")

    return {
        "next_action": result.action,
        "follow_up_question": follow_up_question,
        "react_scratchpad": scratchpad,
        "anchor_assessment": f"Iterative Confidence: {result.confidence}"
    }

async def execute_action_node(state: InterviewerState) -> InterviewerState:
    """Route edges or prepare state depending on LLM decision."""
    action = state.get("next_action")
    anchor_id = state.get("current_anchor_id")
    completed = list(state.get("completed_anchors", []))
    
    if action == "acknowledge_move":
        if anchor_id and anchor_id not in completed:
            completed.append(anchor_id)
            
        next_a = get_next_anchor({"interview_plan": state["interview_plan"], "completed_anchors": completed})
        
        # We append the next anchor's opening question to the acknowledgement seamlessly
        message = state.get("follow_up_question", "")
        if next_a:
            message += f"\n\n{next_a['opening_question']}"
            return {
                "completed_anchors": completed,
                "current_anchor_id": next_a["id"],
                "current_anchor_turns": 1,
                "follow_up_question": message 
            }
        else:
            # no more anchors
             return {
                "completed_anchors": completed,
                "current_anchor_id": "",
                "next_action": "close",
                "follow_up_question": state.get("follow_up_question", "")
            }
    
    return {
        "completed_anchors": completed,
        "current_anchor_turns": state.get("current_anchor_turns", 0) + 1
    }

async def save_exchange_node(state: InterviewerState) -> InterviewerState:
    """Save full exchange to DB including react_scratchpad."""
    db = state["db"]
    session_id = state["session_id"]
    
    # We save what the candidate just said, and what the agent reasoned
    exchange = Exchange(
        session_id=uuid.UUID(session_id),
        turn_number=len(state.get("exchanges", [])) + 1,
        question=state.get("follow_up_question", ""), # The question that was just asked
        candidate_answer=state.get("last_candidate_answer", ""),
        react_scratchpad=state.get("react_scratchpad", "")
    )
    
    db.add(exchange)
    await db.commit()
    await db.refresh(exchange)
    
    # Remove local evaluation and instead signal the websocket/controller to trigger the Celery task
    anchor = get_current_anchor(state)
    send_fn = state["send_fn"]

    await send_fn({
        "type": "trigger_evaluation",
        "exchange_id": str(exchange.id),
        "anchor": anchor,
        "interviewer_confidence": 3
    })
    
    ex_list = list(state.get("exchanges", []))
    ex_list.append({
        "question": state.get("follow_up_question", ""),
        "answer": state.get("last_candidate_answer", "")
    })
    
    send_fn = state["send_fn"]
    
    if state.get("next_action") != "close":
        await send_fn({
             "type": "question",
             "text": state.get("follow_up_question", "")
        })
    
    return {
        "exchanges": ex_list,
        "last_candidate_answer": "",
        "react_scratchpad": ""
    }

def execute_action_condition(state: InterviewerState) -> str:
    if state.get("next_action") == "close":
        return "close_interview"
    return "wait_answer"

async def close_interview_node(state: InterviewerState) -> InterviewerState:
    """Deliver closing statement."""
    plan = state.get("interview_plan", {})
    closing = plan.get("closing_statement", "This concludes the interview. Thank you!")
    
    send_fn = state["send_fn"]
    await send_fn({
         "type": "session_complete",
         "message": closing
    })
    
    # Trigger report generation here if needed.
    return {"session_complete": True}

# ──────────────────────────────────────────────────────────────────────────────
# Graph Assembly
# ──────────────────────────────────────────────────────────────────────────────

def build_react_interview_graph() -> StateGraph:
    graph = StateGraph(InterviewerState)
    
    graph.add_node("open_interview", open_interview_node)
    graph.add_node("wait_answer", wait_answer_node)
    graph.add_node("react_reasoning", react_reasoning_node)
    graph.add_node("execute_action", execute_action_node)
    graph.add_node("save_exchange", save_exchange_node)
    graph.add_node("close_interview", close_interview_node)
    
    graph.set_entry_point("open_interview")
    
    graph.add_edge("open_interview", "wait_answer")
    graph.add_conditional_edges("wait_answer", wait_answer_condition, {"react_reasoning": "react_reasoning", "end": END})
    
    graph.add_edge("react_reasoning", "execute_action")
    
    graph.add_edge("execute_action", "save_exchange")
    graph.add_conditional_edges("save_exchange", execute_action_condition, {
        "wait_answer": "wait_answer",
        "close_interview": "close_interview"
    })
    
    graph.add_edge("close_interview", END)
    
    return graph

interviewer_react_app = build_react_interview_graph().compile()

async def run_interview_graph(session_id: str, session_plan: dict, send_fn: Any, recv_fn: Any, db: Any):
    """
    Runner for the ReAct Interviewer agent inside a WebSocket connection.
    Executes until the interview reaches END.
    """
    initial_state = {
        "session_id": session_id,
        "interview_plan": session_plan,
        "exchanges": [],
        "completed_anchors": [],
        "send_fn": send_fn,
        "recv_fn": recv_fn,
        "db": db
    }
    
    config = {"recursion_limit": 150}
    await interviewer_react_app.ainvoke(initial_state, config=config)
