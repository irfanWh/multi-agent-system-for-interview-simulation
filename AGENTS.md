# InterviewAI — 6-Agent Architecture

> Read `CONTEXT.md` first for the full project overview.

---

## Architecture Philosophy

The system uses a **micro-segmented multi-agent architecture**. There is **no single master LangGraph graph** connecting all agents. Instead, agents are individual LangGraph workflows called sequentially by **FastAPI endpoints** and **Celery tasks**.

```
[API Request]
     ↓
Profile Analyzer        ← Called by /tools/analyze-cv (async Celery task)
     ↓
Match Analyzer          ← Called by /tools/match (async Celery task)
     ↓
Interview Planner       ← Called by POST /sessions/ (inline async)
     ↓
Orchestrator            ← Called by POST /sessions/ (inline async, after Planner)
     ↓
[Session saved to DB with session_plan]
     ↓
Interviewer (ReAct)     ← Called by WebSocket /ws/session/{id} (real-time)
     ↓
Evaluator               ← Called by Celery (after each exchange)
     ↓
Report Generator        ← Called by Celery (after session_complete)
```

---

## Agent 1 — Profile Analyzer

**File:** `backend/app/agents/profile_analyzer.py`  
**Triggered by:** `POST /tools/analyze-cv` or resume upload  
**Purpose:** Extract structured skills and profile from raw CV text  

### What it does:
1. Takes raw CV text as input
2. Runs a LangGraph graph with structured LLM output
3. Returns a structured `AnalyzedProfile`:
   - `candidate_name`, `contact_info`
   - `skills`: categorized (languages, frameworks, databases, cloud, soft_skills)
   - `experience_entries`: with company, role, dates, achievements
   - `education`, `certifications`
   - `experience_level`: `junior | mid | senior | lead` (calibrated)
   - `priority_domains`: list of domains to focus on in the interview
   - `strengths`, `potential_gaps`

### Output stored in:
`Resume.analyzed_profile` (JSONB column in PostgreSQL)

---

## Agent 2 — Match Analyzer

**File:** `backend/app/agents/match_analyzer.py`  
**Triggered by:** `POST /tools/match` endpoint  
**Purpose:** Cross-reference CV vs Job Description, identify gaps and fit  

### What it does:
- Takes `cv_text` + `job_description` as input
- Returns a `MatchReport`:
  - `overall_fit_score` (0-100)
  - `matched_skills`, `missing_skills`
  - `critical_gaps`, `overqualified_areas`
  - `recommended_focus_areas`

### Caching:
Uses `MatchCache` table (keyed by `resume_id + SHA-256(job_description)`) to avoid rerunning the same analysis.

---

## Agent 3 — Interview Planner

**File:** `backend/app/agents/interview_planner.py`  
**Triggered by:** `POST /sessions/` (inline, not Celery)  
**Purpose:** Define the interview *strategy* — what to evaluate and why

### Responsibility:
> "Defines the interview strategy and identifies what should be evaluated."

### What it does:
- Takes: `cv_text`, `job_description`, `match_report`, `interview_config`, `previously_used_openers`
- Generates an `InterviewPlan` with a list of `InterviewAnchor` objects
- Each anchor represents a **topic to probe** during the interview

### InterviewAnchor structure (defined in `models/schemas.py`):
```python
class InterviewAnchor(BaseModel):
    id: str
    type: str          # "project" | "skill" | "gap" | "soft_skill"
    title: str
    cv_reference: str
    jd_relevance: str
    opening_question: str
    what_to_listen_for: List[str]
    follow_up_directions: List[str]
    red_flags: List[str]
    time_allocation_minutes: int
    priority: int
    position_in_flow: str  # "opener" | "core" | "closer"
    # Added for hybrid mode:
    reference_answer: Optional[str]   # filled by Orchestrator if Qdrant match found
    source: Optional[str]             # "planner_generated" | "qdrant_rag"
    evaluation_mode: Optional[str]    # "llm_only" | "hybrid_similarity"
```

### Behavioral Mode Special Rule:
When `interview_type == "behavioral"`, the interview MUST start with a personal "tell me about yourself" question. NO technical project or architecture questions in the opening.

### Output:
`InterviewPlan` dict saved as `Session.session_plan` (after Orchestrator enrichment)

---

## Agent 4 — Orchestrator

**File:** `backend/app/agents/orchestrator.py`  
**Triggered by:** `POST /sessions/` (inline, called after Planner)  
**Purpose:** Build the final question set by enriching Planner anchors with RAG

### Responsibility:
> "Builds the final question set by retrieving standardized questions from Qdrant using the Planner anchors."

### What it does:
- Receives `planner_output` (the full `InterviewPlan` dict from the Planner)
- Iterates over every anchor
- **For `type == "project"` anchors:** Skips Qdrant (too personal), keeps `source = "planner_generated"`, `evaluation_mode = "llm_only"`
- **For skill/gap/soft_skill anchors:** Queries Qdrant `questions_bank` collection for a semantically similar standardized question
  - If found: replaces `opening_question` with Qdrant's `question_text`, sets `reference_answer`, `source = "qdrant_rag"`, `evaluation_mode = "hybrid_similarity"`
  - If not found: keeps Planner question, `source = "planner_generated"`, `evaluation_mode = "llm_only"`

### Key function:
```python
async def run_orchestrator(planner_output: dict, job_profile: dict) -> dict
```
Returns `{"session_plan": enriched_planner_output}` or `{"error": "..."}`.

### LangGraph graph:
Single node: `fetch_questions_node → END`

---

## Agent 5 — Interviewer (ReAct)

**File:** `backend/app/agents/interviewer.py`  
**Triggered by:** WebSocket `/ws/session/{session_id}`  
**Purpose:** Conduct the real-time interview using ReAct reasoning

### Architecture:
Uses the **ReAct (Reasoning + Acting)** pattern. The LLM thinks step-by-step before every response.

### LangGraph nodes:
```
open_interview → wait_answer → react_reasoning → execute_action → save_exchange → (loop or close)
```

### Node responsibilities:
| Node | What it does |
|---|---|
| `open_interview_node` | Sends greeting + first anchor's opening_question via WebSocket |
| `wait_answer_node` | Blocks until candidate replies (text or voice-transcribed) |
| `react_reasoning_node` | LLM reasons: Observe → Assess → Decide action (`follow_up \| probe_gap \| acknowledge_move \| close`) |
| `execute_action_node` | If `acknowledge_move`: marks anchor complete, loads next anchor's question |
| `save_exchange_node` | Saves Exchange to DB, sends next question via WebSocket, triggers Celery `evaluate_exchange_task` |
| `close_interview_node` | Sends `session_complete` + triggers `generate_report_task` Celery task |

### IMPORTANT — Bug fixed:
- First message ALWAYS uses a generic greeting (not the LLM-generated `opening_statement`) to prevent double questions.
- ReAct prompt instructs LLM NOT to ask questions during `acknowledge_move` (system appends next question automatically).

### Behavioral Mode Guard:
In the `react_reasoning_node`, there is a **Question Guard** that detects if the LLM generates a technical question during a behavioral interview and rewrites it.

### Voice Mode:
WebSocket supports binary audio frames → Whisper STT → text → agent. TTS: agent response → streamed back as binary audio frames.

---

## Agent 6 — Report Generator

**File:** `backend/app/agents/report_generator.py`  
**Triggered by:** Celery task `generate_report_task` (after `session_complete`)  
**Purpose:** Generate comprehensive PDF performance report

### What it does:
- Loads all Exchanges + Evaluations for the session
- LangGraph graph runs a multi-step report assembly
- Generates:
  - `global_score` (weighted average)
  - `competency_breakdown`: dict of `{category: {score, insights}}`
  - `action_plan`: personalized improvement roadmap
  - Exports PDF to MinIO (S3-compatible storage)
  - Saves `Report` record to DB

---

## Evaluator (Not an LangGraph Agent — Celery Task)

**File:** `backend/app/agents/evaluator.py`  
**Triggered by:** Celery `evaluate_exchange_task` (after each exchange)

### Hybrid Scoring Formula:
```
Score Final = (LLM_score × 0.6) + (Cosine_Similarity_score × 0.4)
```
Applied only to `score_accuracy`. Other scores (depth, clarity, star) remain LLM-only.

### When hybrid scoring applies:
Only when `anchor["evaluation_mode"] == "hybrid_similarity"` (i.e., Qdrant questions with `reference_answer`).

### Cosine Similarity calculation:
```python
# In qdrant_service.py
async def compute_similarity(text1: str, text2: str) -> float
```
Uses `nomic-embed-text-v1.5` via Groq API → 768-dim vectors → cosine similarity.

### Rubric weights by anchor type:
| Anchor Type | Accuracy | Depth | Clarity | STAR | Ownership |
|---|---|---|---|---|---|
| `skill` | 50% | 30% | 20% | — | — |
| `project` | 30% | 40% | — | — | 30% |
| `gap` | 40% | 40% | 20% | — | — |
| `soft_skill` | — | 30% | 50% | 20% | — |
| `experience` | 30% | 40% | 30% | — | — |

---

## Qdrant Collections

### `questions_bank`
- **Vector size:** 768 (nomic-embed-text)
- **Distance:** Cosine
- **Payload fields:** `question_text`, `reference_answer`, `domain`, `type`, `level`, `source`
- **Indexed fields:** `domain`, `type`, `level`, `source` (keyword indexes for fast filtering)
- **Seeded with:** ~2,292 questions from 5 Kaggle JSONL datasets

### `candidate_memories`
- **Vector size:** 768
- **Payload fields:** `user_id`, `session_id`, `question`, `answer_summary`
- **Used for:** Future personalized follow-up (not yet implemented in production)

---

## Celery Tasks

| Task | File | Triggered by |
|---|---|---|
| `evaluate_exchange_task` | `tasks/evaluate.py` | WebSocket `save_exchange_node` |
| `generate_report_task` | `tasks/report.py` | WebSocket `close_interview_node` |

Celery broker: **Redis** (`redis://redis:6379/0`)
