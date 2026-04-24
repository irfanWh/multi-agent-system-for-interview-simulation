"""
Tests for the ReAct Interviewer loop.

Exercises:
- InterviewPlanner produces structured anchors
- ReAct reasoning references content from the previous answer
- react_scratchpad is non-empty and contains OBSERVE/ASSESS keywords
- Agent does NOT ask from a pre-written static list (responses are contextual)
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


# ─────────────────────────────────────────────
# Sample fixtures
# ─────────────────────────────────────────────

SAMPLE_CV = """
Name: Alice Martin
Experience:
  - Lead ML Engineer at DataCorp (2021-2024)
    * Built a real-time recommendation engine using PyTorch + Redis on AWS ECS
    * Led a team of 4 engineers
  - Data Scientist at AnalyticsCo (2019-2021)
    * Built NLP pipelines, deployed models with FastAPI
Education: MSc Computer Science, Paris Saclay 2019
Skills: Python, PyTorch, Kubernetes, Redis, FastAPI, AWS
"""

SAMPLE_JD = """
Job Title: Senior ML Engineer
Requirements:
  - 5+ years ML experience in production
  - Strong Kubernetes and container orchestration
  - Experience leading engineering teams
  - Vector database experience (Qdrant, Pinecone or similar)
  - Real-time inference pipelines
"""

SAMPLE_MATCH_REPORT = {
    "match_score": 72,
    "missing_skills": ["vector databases", "Qdrant", "Pinecone"],
    "strength_areas": ["PyTorch", "AWS", "Team leadership"],
    "focus_areas": ["vector search", "team leadership depth"]
}

SAMPLE_PLAN = {
    "candidate_name": "Alice Martin",
    "role": "Senior ML Engineer",
    "total_duration_minutes": 30,
    "opening_statement": "Hello Alice, I'm Alex from the hiring team. Let's have a focused technical discussion.",
    "closing_statement": "Thank you Alice, that was very insightful. We'll be in touch shortly.",
    "anchors": [
        {
            "id": "anchor-1",
            "type": "project",
            "title": "Recommendation Engine at DataCorp",
            "cv_reference": "Built a real-time recommendation engine using PyTorch + Redis on AWS ECS",
            "jd_relevance": "JD requires real-time inference pipelines — this directly relates",
            "opening_question": "In your CV you mention building a real-time recommendation engine at DataCorp with PyTorch and Redis. Can you walk me through the overall architecture and the key design decisions you made?",
            "what_to_listen_for": ["real-time latency discussion", "Redis role explained", "scale considerations", "ownership of design"],
            "follow_up_directions": ["dig into Redis eviction strategy", "ask about failure modes", "ask about monitoring"],
            "red_flags": ["can't explain why Redis was chosen", "says 'we did it' without explaining their role"],
            "time_allocation_minutes": 8,
            "priority": 1
        },
        {
            "id": "anchor-2",
            "type": "gap",
            "title": "Vector Database Experience",
            "cv_reference": "No vector database mentioned in CV",
            "jd_relevance": "JD requires Qdrant/Pinecone — this is a gap",
            "opening_question": "The role involves designing vector search pipelines. What's your experience with vector databases like Qdrant or Pinecone?",
            "what_to_listen_for": ["awareness of embedding-based search", "willingness to learn", "adjacent experience"],
            "follow_up_directions": ["ask if they've used FAISS", "ask how they would approach learning it"],
            "red_flags": ["claims deep experience without evidence", "dismisses the requirement"],
            "time_allocation_minutes": 6,
            "priority": 2
        }
    ],
    "opening_anchor_id": "anchor-2"
}


# ─────────────────────────────────────────────
# Test: Interview Planner produces valid schema
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_planner_produces_valid_structure():
    """The InterviewPlanner must produce an InterviewPlan with non-empty anchors."""
    from app.agents.interview_planner import run_interview_planner

    result = await run_interview_planner(
        cv_text=SAMPLE_CV,
        job_description=SAMPLE_JD,
        match_report=SAMPLE_MATCH_REPORT,
        interview_config={"interview_type": "technical", "duration": 30, "focus_areas": ["vector search"]}
    )

    assert not result.get("error"), f"Planner returned error: {result.get('error')}"
    plan = result.get("interview_plan")
    assert plan is not None, "No interview_plan in result"
    assert len(plan.get("anchors", [])) >= 2, "Plan must have at least 2 anchors"
    
    for anchor in plan["anchors"]:
        assert "opening_question" in anchor, "Each anchor must have opening_question"
        assert anchor["opening_question"].strip(), "opening_question must not be empty"
        assert "what_to_listen_for" in anchor
        assert "follow_up_directions" in anchor
        assert "red_flags" in anchor
        assert anchor.get("cv_reference"), "Each anchor must reference something from the CV"
        assert anchor.get("position_in_flow") in ["opener", "core", "closer"]

    assert plan.get("opening_anchor_id") is not None, "opening_anchor_id must be provided"
    
@pytest.mark.asyncio
async def test_opener_is_not_most_impressive_project():
    from app.agents.interview_planner import run_interview_planner

    result = await run_interview_planner(
        cv_text=SAMPLE_CV,
        job_description=SAMPLE_JD,
        match_report=SAMPLE_MATCH_REPORT,
        interview_config={"interview_type": "technical", "duration": 30, "focus_areas": ["vector search"]}
    )
    plan = result.get("interview_plan")
    
    opener_id = plan["opening_anchor_id"]
    opener = next((a for a in plan["anchors"] if a["id"] == opener_id), None)
    
    assert opener is not None, "Opener anchor not found in plan anchors"
    assert opener["position_in_flow"] == "opener", "Opening anchor must have position_in_flow='opener'"
    # The opener should not be the most complex project (RAG pipeline/Recommendation engine)
    title_lower = opener["title"].lower()
    assert "rag" not in title_lower, "Opener should not be the most impressive RAG project"
    assert "recommendation" not in title_lower, "Opener should not be the recommendation engine"

@pytest.mark.asyncio
async def test_flow_order_is_opener_core_closer():
    from app.agents.interview_planner import run_interview_planner
    
    result = await run_interview_planner(
        cv_text=SAMPLE_CV,
        job_description=SAMPLE_JD,
        match_report=SAMPLE_MATCH_REPORT,
        interview_config={"interview_type": "technical", "duration": 30, "focus_areas": ["vector search"]}
    )
    plan = result.get("interview_plan")
    positions = [a["position_in_flow"] for a in plan["anchors"]]
    
    # Check that at least we have opener and core
    assert "opener" in positions
    
@pytest.mark.asyncio
async def test_different_sessions_use_different_openers():
    from app.agents.interview_planner import run_interview_planner
    
    result1 = await run_interview_planner(
        cv_text=SAMPLE_CV,
        job_description=SAMPLE_JD,
        match_report=SAMPLE_MATCH_REPORT,
        interview_config={"interview_type": "technical", "duration": 30, "focus_areas": []},
        previously_used_openers=[]
    )
    plan1 = result1.get("interview_plan")
    opener1_id = plan1["opening_anchor_id"]
    opener1 = next((a for a in plan1["anchors"] if a["id"] == opener1_id), None)
    
    result2 = await run_interview_planner(
        cv_text=SAMPLE_CV,
        job_description=SAMPLE_JD,
        match_report=SAMPLE_MATCH_REPORT,
        interview_config={"interview_type": "technical", "duration": 30, "focus_areas": []},
        previously_used_openers=[opener1["title"]]
    )
    plan2 = result2.get("interview_plan")
    
    # They shouldn't pick the same anchor if possible. Depending on the LLM, it should vary.
    assert plan1["opening_anchor_id"] != plan2["opening_anchor_id"]
# Test: ReAct reason_node populates scratchpad
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_react_scratchpad_contains_reasoning():
    """react_reasoning_node must populate react_scratchpad with OBSERVE and ASSESS sections."""
    from app.agents.interviewer import react_reasoning_node, InterviewerState

    state: InterviewerState = {
        "session_id": str(uuid4()),
        "interview_plan": SAMPLE_PLAN,
        "current_anchor_id": "anchor-1",
        "current_anchor_turns": 1,
        "exchanges": [],
        "last_candidate_answer": "We used Redis mainly for caching the user embedding lookups. The recommendation engine ran on ECS with auto-scaling. I designed the whole pipeline.",
        "completed_anchors": [],
        "send_fn": AsyncMock(),
        "recv_fn": AsyncMock(),
        "db": MagicMock()
    }

    result = await react_reasoning_node(state)

    scratchpad = result.get("react_scratchpad", "")
    assert scratchpad, "react_scratchpad must not be empty"
    assert "OBSERVE" in scratchpad, "Scratchpad must contain OBSERVE section"
    assert "ASSESS" in scratchpad, "Scratchpad must contain ASSESS section"
    assert result.get("next_action") in ("follow_up", "probe_gap", "acknowledge_move", "close")


# ─────────────────────────────────────────────
# Test: Follow-up references prior answer content
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_follow_up_references_candidate_answer():
    """
    When action=follow_up, message_to_candidate must not be a generic template —
    it must reference something from last_candidate_answer.
    """
    from app.agents.interviewer import react_reasoning_node, InterviewerState
    
    candidate_answer = "I chose HNSW indexing because it gave us better recall at the scale we needed. We tuned ef=200."
    
    state: InterviewerState = {
        "session_id": str(uuid4()),
        "interview_plan": SAMPLE_PLAN,
        "current_anchor_id": "anchor-1",
        "current_anchor_turns": 1,
        "exchanges": [],
        "last_candidate_answer": candidate_answer,
        "completed_anchors": [],
        "send_fn": AsyncMock(),
        "recv_fn": AsyncMock(),
        "db": MagicMock()
    }

    result = await react_reasoning_node(state)

    action = result.get("next_action")
    follow_up_msg = result.get("follow_up_question", "")

    if action in ("follow_up", "probe_gap"):
        # A good follow-up picks on a specific detail from the candidate's answer
        generic_phrases = [
            "tell me more",
            "can you elaborate",
            "please explain",
            "could you describe"
        ]
        assert follow_up_msg.strip(), "follow_up_question must not be empty"
        # At least something specific from their answer should be referenced
        answer_keywords = ["HNSW", "hnsw", "recall", "ef", "200", "scale", "indexing"]
        referenced_something = any(kw.lower() in follow_up_msg.lower() for kw in answer_keywords)
        assert referenced_something, (
            f"Follow-up question does not reference candidate's answer keywords.\n"
            f"Answer: {candidate_answer}\n"
            f"Follow-up: {follow_up_msg}"
        )


# ─────────────────────────────────────────────
# Test: Anchor transition stays within time budget
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_anchor_transition_after_sufficient_turns():
    """After hitting the time_allocation_minutes threshold, agent should acknowledge_move."""
    from app.agents.interviewer import react_reasoning_node, InterviewerState

    # Simulate many turns (7 out of 8-min budget)
    exchanges = [{"question": f"Q{i}", "answer": "A reasonable answer with good detail."} for i in range(6)]

    state: InterviewerState = {
        "session_id": str(uuid4()),
        "interview_plan": SAMPLE_PLAN,
        "current_anchor_id": "anchor-1",
        "current_anchor_turns": 7,  # nearly at the 8-minute limit
        "exchanges": exchanges,
        "last_candidate_answer": "Yes, I think I've covered the key aspects of the recommendation engine design.",
        "completed_anchors": [],
        "send_fn": AsyncMock(),
        "recv_fn": AsyncMock(),
        "db": MagicMock()
    }

    result = await react_reasoning_node(state)
    action = result.get("next_action")

    # At 7 turns for an 8-min anchor, the agent should strongly prefer to move on
    assert action in ("acknowledge_move", "close"), (
        f"Expected acknowledge_move or close after {state['current_anchor_turns']} turns, got {action}"
    )
