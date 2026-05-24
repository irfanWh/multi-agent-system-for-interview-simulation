import logging
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

from app.services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Graph State
# ──────────────────────────────────────────────────────────────────────────────

class OrchestratorState(TypedDict, total=False):
    planner_output: dict
    job_profile: dict
    session_plan: Optional[dict]
    error: Optional[str]

# ──────────────────────────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────────────────────────

async def fetch_questions_node(state: OrchestratorState) -> OrchestratorState:
    """Fetch relevant questions from Qdrant based on planner anchors."""
    if state.get("error"):
        return state
        
    try:
        qdrant = QdrantService.get_instance()
        planner_output = state.get("planner_output", {})
        profile = state.get("job_profile", {})
        
        # Fallback to junior if missing
        level = profile.get("calibrated_level", "junior")
        anchors = planner_output.get("anchors", [])
        
        used_ids = set()
        
        for anchor in anchors:
            # Map planner anchor types to Qdrant types
            q_type = "behavioral" if anchor.get("type") in ["soft_skill", "behavioral"] else "technical"
            domain = anchor.get("title", "general")
            
            # Avoid overwriting specific personal projects with standardized questions
            if anchor.get("type") == "project":
                anchor["source"] = "planner_generated"
                anchor["evaluation_mode"] = "llm_only"
                continue

            # Build semantic search query
            query = f"{domain} {q_type} interview question for {level} level candidate"
            
            # Fetch from Qdrant
            results = await qdrant.search_questions(
                query=query,
                filters={"level": level, "type": q_type},
                top_k=3
            )
            
            # Pick best unused
            chosen = None
            for r in results:
                if r["id"] not in used_ids:
                    chosen = r
                    used_ids.add(r["id"])
                    break
                    
            if chosen:
                anchor["opening_question"] = chosen["question_text"]
                anchor["reference_answer"] = chosen.get("reference_answer", "")
                anchor["source"] = "qdrant_rag"
                anchor["evaluation_mode"] = "hybrid_similarity"
            else:
                anchor["source"] = "planner_generated"
                anchor["evaluation_mode"] = "llm_only"
                
        return {"session_plan": planner_output}
    except Exception as exc:
        logger.error("fetch_questions_node error: %s", exc)
        return {"error": f"Fetching questions failed: {exc}"}

# ──────────────────────────────────────────────────────────────────────────────
# Graph Assembly
# ──────────────────────────────────────────────────────────────────────────────

def build_orchestrator_graph() -> StateGraph:
    graph = StateGraph(OrchestratorState)
    
    graph.add_node("fetch_questions", fetch_questions_node)
    
    graph.set_entry_point("fetch_questions")
    graph.add_edge("fetch_questions", END)
    
    return graph

orchestrator_app = build_orchestrator_graph().compile()

async def run_orchestrator(
    planner_output: dict,
    job_profile: dict
) -> dict:
    """
    Public entry point: run the Orchestrator agent to enrich planner output.
    Returns the final state dict containing 'session_plan' or 'error'.
    """
    initial_state: OrchestratorState = {
        "planner_output": planner_output,
        "job_profile": job_profile
    }
    result = await orchestrator_app.ainvoke(initial_state)
    return result
