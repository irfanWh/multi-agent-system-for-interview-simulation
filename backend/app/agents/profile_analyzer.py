"""
Agent 1 — Profile Analyzer (LangGraph StateGraph)

Analyses a candidate's CV text and produces a structured JobProfile
containing detected skills, skill gaps, calibrated level, and interview recommendations.

Uses: ChatGroq (llama-3.1-70b-versatile), Qdrant for RAG enrichment.
"""
import os
import logging
from typing import Optional, List, TypedDict

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic output schema
# ──────────────────────────────────────────────────────────────────────────────

class JobProfile(BaseModel):
    """Structured output from the Profile Analyzer agent."""
    formations: List[str] = Field(default_factory=list, description="Education / degrees / training programmes")
    experiences: List[str] = Field(default_factory=list, description="Professional experiences summarised")
    projects: List[str] = Field(default_factory=list, description="Notable projects")
    certifications: List[str] = Field(default_factory=list, description="Certifications held")
    detected_skills: List[str] = Field(default_factory=list, description="Technical and soft skills detected in the CV")
    skill_gaps: List[str] = Field(default_factory=list, description="Skills expected for the target role but missing from the CV")
    calibrated_level: str = Field(default="junior", description="Calibrated seniority level: junior / mid / senior / lead")
    priority_domains: List[str] = Field(default_factory=list, description="Top 3 knowledge domains to cover during the interview")
    recommended_question_types: List[str] = Field(default_factory=list, description="Recommended question types: technical, behavioral, system_design")
    profile_summary: str = Field(default="", description="2-3 sentence human-readable profile summary")


# ──────────────────────────────────────────────────────────────────────────────
# Graph state
# ──────────────────────────────────────────────────────────────────────────────

class ProfileAnalyzerState(TypedDict, total=False):
    cv_text: str
    target_role: str
    experience_level: str
    job_description: Optional[str]
    extracted_profile: Optional[dict]
    rag_context: Optional[str]
    error: Optional[str]


# ──────────────────────────────────────────────────────────────────────────────
# LLM factory (with retry wrapper)
# ──────────────────────────────────────────────────────────────────────────────

def _get_llm():
    """Return a ChatGroq instance configured for structured output."""
    from langchain_groq import ChatGroq

    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
    )


def _invoke_with_retries(chain, payload: dict, max_retries: int = 3):
    """Invoke a LangChain chain with retry logic."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return chain.invoke(payload)
        except Exception as exc:
            last_exc = exc
            logger.warning("LLM attempt %d/%d failed: %s", attempt, max_retries, exc)
    raise last_exc  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────────────────────
# Node 1 — Parse CV
# ──────────────────────────────────────────────────────────────────────────────

PARSE_CV_PROMPT = """\
You are an expert technical recruiter and CV analyst.

Given the following CV text, extract structured information about the candidate.
Think step-by-step:
1. First, identify all education/training (formations).
2. Then, list professional experiences.
3. Identify notable projects.
4. List certifications.
5. Extract all technical and soft skills.
6. Write a 2-3 sentence summary of the candidate.

### FEW-SHOT EXAMPLE ###

CV Text: "John Doe — Software Engineer. MSc Computer Science, MIT 2020. \
3 years at Google working on distributed systems in Go and Python. \
Built a real-time data pipeline processing 1M events/sec. \
AWS Certified Solutions Architect. Skills: Python, Go, Kubernetes, PostgreSQL, gRPC."

Expected output:
- formations: ["MSc Computer Science, MIT 2020"]
- experiences: ["3 years at Google — distributed systems in Go and Python"]
- projects: ["Real-time data pipeline processing 1M events/sec"]
- certifications: ["AWS Certified Solutions Architect"]
- detected_skills: ["Python", "Go", "Kubernetes", "PostgreSQL", "gRPC", "distributed systems"]
- profile_summary: "Experienced software engineer with a strong distributed systems background. \
3 years at Google with hands-on expertise in Python, Go, and cloud infrastructure."

### END EXAMPLE ###

Now analyse this CV:

Target role: {target_role}
Experience level (self-reported): {experience_level}

CV Text:
{cv_text}
"""


def parse_cv_node(state: ProfileAnalyzerState) -> ProfileAnalyzerState:
    """Extract structured CV information using the LLM."""
    try:
        llm = _get_llm()
        structured_llm = llm.with_structured_output(JobProfile)

        prompt_text = PARSE_CV_PROMPT.format(
            cv_text=state["cv_text"],
            target_role=state["target_role"],
            experience_level=state["experience_level"],
        )
        
        if state.get("job_description"):
            prompt_text += f"\n\nJob description provided by the candidate:\n{state['job_description']}\n\nUse this to identify skill gaps, calibrate the expected level, and determine priority domains more precisely."

        result: JobProfile = _invoke_with_retries(
            structured_llm,
            prompt_text,
        )
        return {"extracted_profile": result.model_dump(), "error": None}
    except Exception as exc:
        logger.error("parse_cv_node failed: %s", exc)
        return {"extracted_profile": None, "error": f"CV parsing failed: {exc}"}


# ──────────────────────────────────────────────────────────────────────────────
# Node 2 — Enrich with RAG (Qdrant)
# ──────────────────────────────────────────────────────────────────────────────

async def enrich_with_rag_node(state: ProfileAnalyzerState) -> ProfileAnalyzerState:
    """Search Qdrant for similar questions to calibrate skill assessment."""
    if state.get("error"):
        # Skip RAG but must still return a valid state key
        return {"rag_context": ""}

    try:
        from app.services.qdrant_service import QdrantService

        qdrant = QdrantService.get_instance()
        profile = state.get("extracted_profile") or {}
        skills = profile.get("detected_skills", [])

        # Search questions_bank for questions related to the candidate's skills
        query = f"{state['target_role']} {' '.join(skills[:5])}"
        if state.get("job_description"):
            # Use job description logic as requested to enhance similarity search
            query += " " + state["job_description"][:500]

        results = await qdrant.search_questions(
            query=query,
            filters={"level": state.get("experience_level", "junior")},
            top_k=5,
        )

        rag_context = "\n".join(
            f"- [{r['domain']}/{r['level']}] {r['question_text']}" for r in results
        )
        return {"rag_context": rag_context}
    except Exception as exc:
        logger.warning("RAG enrichment failed (non-fatal): %s", exc)
        return {"rag_context": ""}


# ──────────────────────────────────────────────────────────────────────────────
# Node 3 — Build final profile
# ──────────────────────────────────────────────────────────────────────────────

BUILD_PROFILE_PROMPT = """\
You are a senior technical interviewer calibrating a candidate profile.

Here is the parsed CV profile:
{parsed_profile}

Target role: {target_role}
Self-reported level: {experience_level}

Related interview questions from our database (for context on what this level requires):
{rag_context}

Think step-by-step:
1. Compare the candidate's detected skills against what is typically required for \
a {target_role} at the {experience_level} level.
2. Identify skill gaps — skills the role needs but the CV doesn't mention.
3. Calibrate the actual level (junior/mid/senior/lead) based on evidence, not self-report.
4. Pick the top 3 priority domains the interview should focus on.
5. Recommend question types (technical, behavioral, system_design) based on the gaps.
6. Preserve all formations, experiences, projects, certifications from the parsed CV.

Produce the final calibrated profile.
"""


def build_profile_node(state: ProfileAnalyzerState) -> ProfileAnalyzerState:
    """Produce the final calibrated JobProfile using RAG context."""
    if state.get("error"):
        # Propagate the error, return the existing extracted_profile as-is
        return {"extracted_profile": state.get("extracted_profile"), "error": state.get("error")}

    try:
        llm = _get_llm()
        structured_llm = llm.with_structured_output(JobProfile)

        parsed_profile = state.get("extracted_profile") or {}
        rag_context = state.get("rag_context") or "No additional context available."

        result: JobProfile = _invoke_with_retries(
            structured_llm,
            BUILD_PROFILE_PROMPT.format(
                parsed_profile=parsed_profile,
                target_role=state["target_role"],
                experience_level=state["experience_level"],
                rag_context=rag_context,
            ),
        )
        return {"extracted_profile": result.model_dump(), "error": None}
    except Exception as exc:
        logger.error("build_profile_node failed: %s", exc)
        return {"extracted_profile": state.get("extracted_profile"), "error": f"Profile calibration failed: {exc}"}


# ──────────────────────────────────────────────────────────────────────────────
# Graph assembly
# ──────────────────────────────────────────────────────────────────────────────

def build_profile_analyzer_graph() -> StateGraph:
    """
    Assemble the 3-node Profile Analyzer graph:
        parse_cv → enrich_with_rag → build_profile → END
    """
    graph = StateGraph(ProfileAnalyzerState)

    graph.add_node("parse_cv", parse_cv_node)
    graph.add_node("enrich_with_rag", enrich_with_rag_node)
    graph.add_node("build_profile", build_profile_node)

    graph.set_entry_point("parse_cv")
    graph.add_edge("parse_cv", "enrich_with_rag")
    graph.add_edge("enrich_with_rag", "build_profile")
    graph.add_edge("build_profile", END)

    return graph


# Compile once at module level for reuse
profile_analyzer_app = build_profile_analyzer_graph().compile()


async def run_profile_analyzer(
    cv_text: str,
    target_role: str | None = None,
    experience_level: str | None = None,
    job_description: str | None = None,
) -> dict:
    """
    Public entry point: run the Profile Analyzer agent.
    Returns the final state dict containing 'extracted_profile' or 'error'.
    """
    initial_state: ProfileAnalyzerState = {
        "cv_text": cv_text,
        "target_role": target_role or "General Role",
        "experience_level": experience_level or "Unknown",
        "job_description": job_description,
    }
    result = await profile_analyzer_app.ainvoke(initial_state)
    return result
