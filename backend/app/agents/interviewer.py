import logging
from typing import List, Dict, Optional, TypedDict, Any
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END
from app.agents.profile_analyzer import _get_llm, _invoke_with_retries
from app.models.orm import Exchange
import uuid

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# State Schema
# ──────────────────────────────────────────────────────────────────────────────

class InterviewerState(TypedDict, total=False):
    session_id: str
    session_plan: dict
    current_turn: int
    exchanges: list[dict]
    last_candidate_answer: str
    awaiting_answer: bool
    silence_count: int
    session_complete: bool
    
    # Internal variables mapping
    has_followed_up: bool
    is_complete: bool
    current_question_text: str
    current_question_full: dict
    
    # Dependencies injected for I/O and DB
    send_fn: Any
    recv_fn: Any
    db: Any

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas for LLM outputs
# ──────────────────────────────────────────────────────────────────────────────

class FormattedQuestion(BaseModel):
    formatted_text: str = Field(description="The question formatted as a natural spoken sentence")

class AnswerEvaluation(BaseModel):
    is_complete: bool = Field(description="True if the candidate has provided a sufficiently complete answer")
    reasoning: str = Field(description="Explanation of why the answer is complete or incomplete")

class FollowUp(BaseModel):
    follow_up_text: str = Field(description="The follow-up prompt addressed to the candidate")

# ──────────────────────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────────────────────

PERSONA = "Tu es un interviewer technique bienveillant mais rigoureux. Tu poses une question à la fois. Tu ne donnes pas les réponses."

FORMAT_QUESTION_PROMPT = """{persona}

Formule la question suivante de façon naturelle et conversationnelle comme si tu parlais au candidat. N'ajoute rien d'autre.
Question originale : {question_text}
Domaine : {domain}
"""

DETECT_INCOMPLETE_PROMPT = """{persona}

Évalue si la réponse du candidat répond suffisamment à la question posée, selon les critères d'évaluation.
Question: {question_text}
Critères attendus:
{criteria}

Réponse du candidat:
{candidate_answer}

L'évaluation doit dire si c'est "complet" ou non. C'est incomplet si c'est hors sujet, trop bref, ou si ça manque un point crucial.
"""

FOLLOW_UP_PROMPT = """{persona}

La réponse du candidat était incomplète. Formule une courte relance (follow-up) pour l'aider à développer ou le recentrer, en utilisant ces indices de relance : 
Indices: {hints}

L'historique récent de cette question :
Question posée: {question_text}
Réponse partielle: {candidate_answer}

Génère juste la phrase de relance naturelle.
"""

# ──────────────────────────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────────────────────────

async def ask_question_node(state: InterviewerState) -> InterviewerState:
    """Pick question at current_turn, format it with interviewer persona."""
    turn = state.get("current_turn", 0)
    session_plan = state.get("session_plan", {})
    questions = session_plan.get("questions", [])
    
    if turn >= len(questions):
        return {"session_complete": True}
        
    current_q = questions[turn]
    
    llm = _get_llm()
    structured_llm = llm.with_structured_output(FormattedQuestion)
    
    result: FormattedQuestion = _invoke_with_retries(
        structured_llm,
        FORMAT_QUESTION_PROMPT.format(
            persona=PERSONA,
            question_text=current_q["question_text"],
            domain=current_q["domain"]
        )
    )
    
    formatted_text = result.formatted_text
    
    # Send via WebSocket
    send_fn = state["send_fn"]
    await send_fn({
        "type": "question",
        "text": formatted_text,
        "turn": turn + 1,
        "total": len(questions)
    })
    
    return {
        "current_question_text": formatted_text,
        "current_question_full": current_q,
        "has_followed_up": False,
        "silence_count": 0,
        "last_candidate_answer": "",
        "awaiting_answer": True
    }


async def wait_answer_node(state: InterviewerState) -> InterviewerState:
    """Receive answer from WebSocket, store in state."""
    recv_fn = state["recv_fn"]
    
    # Wait for the next message
    msg = await recv_fn()
    if msg.get("type") == "disconnect":
        return {"session_complete": True}
        
    answer_text = msg.get("text", "").strip()
    
    silence = state.get("silence_count", 0)
    if not answer_text:
        silence += 1
    else:
        # User spoke
        silence = 0
        
    # Append to cumulative answer for this turn
    cumulative_answer = state.get("last_candidate_answer", "")
    if cumulative_answer and answer_text:
        cumulative_answer += " " + answer_text
    else:
        cumulative_answer = answer_text
        
    return {
        "last_candidate_answer": cumulative_answer,
        "silence_count": silence,
        "awaiting_answer": False
    }


def wait_answer_condition(state: InterviewerState) -> str:
    """If silence_count >= 2 → follow_up; else → detect_incomplete"""
    if state.get("session_complete"):
        return "end"
        
    if state.get("silence_count", 0) >= 2:
        return "follow_up"
    return "detect_incomplete"


async def detect_incomplete_node(state: InterviewerState) -> InterviewerState:
    """LLM check if answer is complete or needs follow-up."""
    # If the user didn't say anything at all, it's obviously incomplete
    ans = state.get("last_candidate_answer", "").strip()
    if not ans:
        return {"is_complete": False}
        
    current_q = state["current_question_full"]
    criteria = "- " + "\n- ".join(current_q.get("evaluation_criteria", []))
    
    llm = _get_llm()
    structured_llm = llm.with_structured_output(AnswerEvaluation)
    
    eval_result: AnswerEvaluation = _invoke_with_retries(
        structured_llm,
        DETECT_INCOMPLETE_PROMPT.format(
            persona=PERSONA,
            question_text=state["current_question_text"],
            criteria=criteria,
            candidate_answer=ans
        )
    )
    
    return {"is_complete": eval_result.is_complete}


def detect_incomplete_condition(state: InterviewerState) -> str:
    """if incomplete → follow_up (max 1 follow-up per question) else → advance_turn"""
    is_complete = state.get("is_complete", False)
    has_followed_up = state.get("has_followed_up", False)
    
    if not is_complete and not has_followed_up:
        return "follow_up"
    return "advance_turn"


async def follow_up_node(state: InterviewerState) -> InterviewerState:
    """Generate contextual follow-up from question's follow_up_hints."""
    current_q = state["current_question_full"]
    hints = "- " + "\n- ".join(current_q.get("follow_up_hints", []))
    
    llm = _get_llm()
    structured_llm = llm.with_structured_output(FollowUp)
    
    result: FollowUp = _invoke_with_retries(
        structured_llm,
        FOLLOW_UP_PROMPT.format(
            persona=PERSONA,
            hints=hints,
            question_text=state["current_question_text"],
            candidate_answer=state.get("last_candidate_answer", "")
        )
    )
    
    follow_up_text = result.follow_up_text
    
    send_fn = state["send_fn"]
    await send_fn({
        "type": "follow_up",
        "text": follow_up_text
    })
    
    # We followed up, so wait for reply again
    return {
        "has_followed_up": True,
        "silence_count": 0
    }


async def advance_turn_node(state: InterviewerState) -> InterviewerState:
    """Save exchange to DB, increment turn, check if session_complete."""
    db = state["db"]
    session_id = state["session_id"]
    turn = state["current_turn"]
    
    exchange = Exchange(
        session_id=uuid.UUID(session_id),
        turn_number=turn + 1,
        question=state.get("current_question_text", ""),
        candidate_answer=state.get("last_candidate_answer", "")
    )
    
    db.add(exchange)
    await db.commit()
    
    new_turn = turn + 1
    session_plan = state.get("session_plan", {})
    total = session_plan.get("total_questions", 0)
    
    is_complete = new_turn >= total
    
    if is_complete:
        send_fn = state["send_fn"]
        await send_fn({
            "type": "session_complete",
            "message": "Merci pour cet entretien. Vos réponses ont bien été enregistrées."
        })
        
    return {
        "current_turn": new_turn,
        "session_complete": is_complete,
        "last_candidate_answer": "",
        "silence_count": 0,
        "has_followed_up": False
    }


def advance_turn_condition(state: InterviewerState) -> str:
    """if session_complete → END else → ask_question"""
    if state.get("session_complete"):
        return "end"
    return "ask_question"


# ──────────────────────────────────────────────────────────────────────────────
# Graph Assembly
# ──────────────────────────────────────────────────────────────────────────────

def build_interview_graph() -> StateGraph:
    graph = StateGraph(InterviewerState)
    
    graph.add_node("ask_question", ask_question_node)
    graph.add_node("wait_answer", wait_answer_node)
    graph.add_node("detect_incomplete", detect_incomplete_node)
    graph.add_node("follow_up", follow_up_node)
    graph.add_node("advance_turn", advance_turn_node)
    
    graph.set_entry_point("ask_question")
    
    graph.add_edge("ask_question", "wait_answer")
    
    graph.add_conditional_edges(
        "wait_answer",
        wait_answer_condition,
        {
            "follow_up": "follow_up",
            "detect_incomplete": "detect_incomplete",
            "end": END
        }
    )
    
    graph.add_conditional_edges(
        "detect_incomplete",
        detect_incomplete_condition,
        {
            "follow_up": "follow_up",
            "advance_turn": "advance_turn"
        }
    )
    
    graph.add_edge("follow_up", "wait_answer")
    
    graph.add_conditional_edges(
        "advance_turn",
        advance_turn_condition,
        {
            "ask_question": "ask_question",
            "end": END
        }
    )
    
    return graph

interviewer_app = build_interview_graph().compile()

async def run_interview_graph(session_id: str, session_plan: dict, send_fn: Any, recv_fn: Any, db: Any):
    """
    Runner for the Interviewer agent inside a WebSocket connection.
    Executes until the interview reaches END.
    """
    initial_state = {
        "session_id": session_id,
        "session_plan": session_plan,
        "current_turn": 0,
        "exchanges": [],
        "last_candidate_answer": "",
        "awaiting_answer": False,
        "silence_count": 0,
        "session_complete": False,
        "has_followed_up": False,
        "send_fn": send_fn,
        "recv_fn": recv_fn,
        "db": db
    }
    
    # LangGraph execution runs asynchronously. Since we use `await recv_fn()` 
    # directly inside the nodes, the graph will correctly yield control to asyncio
    # while waiting for websocket messages!
    config = {"recursion_limit": 150}
    await interviewer_app.ainvoke(initial_state, config=config)
