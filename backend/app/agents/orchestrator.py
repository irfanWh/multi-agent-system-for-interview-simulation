import logging
from typing import List, Dict, Optional, TypedDict, Any
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END
from app.services.qdrant_service import QdrantService
from app.agents.profile_analyzer import _get_llm, _invoke_with_retries

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas
# ──────────────────────────────────────────────────────────────────────────────

class PlannedQuestion(BaseModel):
    order: int
    question_text: str
    domain: str
    type: str  # technical / behavioral / system_design
    difficulty: str  # easy / medium / hard
    evaluation_criteria: List[str] = Field(description="what the evaluator will check")
    follow_up_hints: List[str] = Field(description="relances si réponse incomplète")

class SessionPlan(BaseModel):
    total_questions: int
    questions: List[PlannedQuestion]
    interview_config: Dict[str, Any]

class RubricOutput(BaseModel):
    evaluation_criteria: List[str]
    follow_up_hints: List[str]

# ──────────────────────────────────────────────────────────────────────────────
# Graph State
# ──────────────────────────────────────────────────────────────────────────────

class OrchestratorState(TypedDict, total=False):
    job_profile: dict
    interview_type: str
    duration_minutes: int
    job_description: Optional[str]
    focus_areas: Optional[List[str]]
    
    total_questions: int
    question_slots: List[dict]
    selected_questions: List[dict]
    session_plan: Optional[dict]
    
    error: Optional[str]

# ──────────────────────────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────────────────────────

def plan_questions_node(state: OrchestratorState) -> OrchestratorState:
    """Determine number of questions and calculate specific slots."""
    if state.get("error"):
        return state
        
    try:
        duration = state.get("duration_minutes", 30)
        i_type = state.get("interview_type", "mixed")
        
        # 1 question ≈ 4 min
        total_questions = max(1, duration // 4)
        
        if i_type == "technical":
            tech_count = int(total_questions * 0.8)
            behav_count = total_questions - tech_count
        elif i_type == "behavioral":
            behav_count = int(total_questions * 0.8)
            tech_count = total_questions - behav_count
        else:  # mixed
            tech_count = total_questions // 2
            behav_count = total_questions - tech_count
            
        profile = state.get("job_profile", {})
        
        # Override domains with focus_areas if provided, else priority_domains
        domains = state.get("focus_areas")
        if not domains:
            domains = profile.get("priority_domains", ["general"])
        if not domains:
            domains = ["general"]
            
        slots = []
        domain_idx = 0
        for _ in range(tech_count):
            slots.append({"type": "technical", "domain": domains[domain_idx % len(domains)]})
            domain_idx += 1
            
        for _ in range(behav_count):
            slots.append({"type": "behavioral", "domain": "soft_skills"})
            
        return {
            "total_questions": total_questions,
            "question_slots": slots,
            "error": None
        }
    except Exception as exc:
        logger.error("plan_questions_node error: %s", exc)
        return {"error": f"Planning failed: {exc}"}

async def fetch_questions_node(state: OrchestratorState) -> OrchestratorState:
    """Fetch relevant questions from Qdrant based on planned slots."""
    if state.get("error"):
        return state
        
    try:
        qdrant = QdrantService.get_instance()
        slots = state.get("question_slots", [])
        profile = state.get("job_profile", {})
        
        # Fallback to junior if missing
        level = profile.get("calibrated_level", "junior")
        
        selected = []
        used_ids = set()
        
        for slot in slots:
            q_type = slot["type"]
            domain = slot["domain"]
            
            # Build semantic search query
            query = f"{domain} {q_type} interview question for {level} level candidate"
            if state.get("job_description"):
                query += f" relevant to this job context: {state['job_description'][:400]}"
            
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
            
            # Fallback if all used
            if not chosen and results:
                chosen = results[0]
                
            if chosen:
                selected.append({
                    "question_text": chosen["question_text"],
                    "domain": domain,
                    "type": q_type,
                    "difficulty": level
                })
            else:
                # Fallback purely synthetic if Qdrant is empty
                selected.append({
                    "question_text": f"Can you describe your experience with {domain}?",
                    "domain": domain,
                    "type": q_type,
                    "difficulty": level
                })
                
        return {"selected_questions": selected}
    except Exception as exc:
        logger.error("fetch_questions_node error: %s", exc)
        return {"error": f"Fetching questions failed: {exc}"}

BUILD_RUBRIC_PROMPT = """\
You are an expert technical interviewer and evaluator in the HR domain.

Given the following interview question context, provide an evaluation rubric.
You need to list the key criteria the evaluator should check in the candidate's answer.
You also need to provide 1-2 possible follow-up hints (relances) if the candidate's answer is incomplete.

Question: {question_text}
Domain: {domain}
Type: {type}
Target Level: {difficulty}
Job Context: {job_description}

Use the job description to prioritize criteria that match the specific 
technologies and responsibilities mentioned for this role!

Produce output according to the strictly requested schema.
"""

def build_rubric_node(state: OrchestratorState) -> OrchestratorState:
    """Use the LLM to generate evaluation rubrics for the selected questions."""
    if state.get("error"):
        return state
        
    try:
        llm = _get_llm()
        structured_llm = llm.with_structured_output(RubricOutput)
        
        selected = state.get("selected_questions", [])
        planned_questions = []
        
        for idx, q in enumerate(selected):
            rubric: RubricOutput = _invoke_with_retries(
                structured_llm,
                BUILD_RUBRIC_PROMPT.format(
                    question_text=q["question_text"],
                    domain=q["domain"],
                    type=q["type"],
                    difficulty=q["difficulty"],
                    job_description=state.get("job_description") or "Not provided"
                )
            )
            
            planned_questions.append(
                PlannedQuestion(
                    order=idx + 1,
                    question_text=q["question_text"],
                    domain=q["domain"],
                    type=q["type"],
                    difficulty=q["difficulty"],
                    evaluation_criteria=rubric.evaluation_criteria,
                    follow_up_hints=rubric.follow_up_hints
                )
            )
            
        session_plan = SessionPlan(
            total_questions=len(planned_questions),
            questions=planned_questions,
            interview_config={
                "type": state.get("interview_type"),
                "duration_minutes": state.get("duration_minutes")
            }
        )
        
        return {"session_plan": session_plan.model_dump()}
    except Exception as exc:
        logger.error("build_rubric_node error: %s", exc)
        return {"error": f"Rubric building failed: {exc}"}

# ──────────────────────────────────────────────────────────────────────────────
# Graph Assembly
# ──────────────────────────────────────────────────────────────────────────────

def build_orchestrator_graph() -> StateGraph:
    graph = StateGraph(OrchestratorState)
    
    graph.add_node("plan_questions", plan_questions_node)
    graph.add_node("fetch_questions", fetch_questions_node)
    graph.add_node("build_rubric", build_rubric_node)
    
    graph.set_entry_point("plan_questions")
    graph.add_edge("plan_questions", "fetch_questions")
    graph.add_edge("fetch_questions", "build_rubric")
    graph.add_edge("build_rubric", END)
    
    return graph

orchestrator_app = build_orchestrator_graph().compile()

async def run_orchestrator(
    job_profile: dict, 
    interview_type: str, 
    duration_minutes: int, 
    job_description: str | None = None,
    focus_areas: list[str] | None = None
) -> dict:
    """
    Public entry point: run the Orchestrator agent.
    Returns the final state dict containing 'session_plan' or 'error'.
    """
    initial_state: OrchestratorState = {
        "job_profile": job_profile,
        "interview_type": interview_type,
        "duration_minutes": duration_minutes,
        "job_description": job_description,
        "focus_areas": focus_areas
    }
    result = await orchestrator_app.ainvoke(initial_state)
    return result
