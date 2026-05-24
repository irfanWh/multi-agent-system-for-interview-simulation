# InterviewAI — Full Project Context

> **Purpose:** This file is the **master context document** for the InterviewAI multi-agent interview simulation platform. Read this first before working on any feature.

---

## 🎯 What This System Does

InterviewAI is a full-stack AI-powered interview simulation platform. A candidate:
1. **Uploads their CV** (PDF/DOCX)
2. **Pastes a Job Description** (optional)
3. **Starts an interview session** — the AI plans a personalized interview and conducts it in real-time via text or voice WebSocket
4. **Receives a detailed performance report** with scores, strengths, and an action plan

---

## 🏗️ Tech Stack

### Backend
| Layer | Technology |
|---|---|
| Framework | **FastAPI** 0.110.0 (async) |
| AI/LLM | **Groq** (Llama 3.3-70b via `langchain-groq`) |
| Agent Framework | **LangGraph** 0.2.28 |
| Agent Monitoring | **LangSmith** 0.1.131 |
| Database | **PostgreSQL** (async via SQLAlchemy 2.0 + asyncpg) |
| Vector DB | **Qdrant** (local Docker, port 6333) |
| Embeddings | **nomic-embed-text-v1.5** via Groq API (768-dim), SHA-512 fallback |
| Task Queue | **Celery** + **Redis** (async evaluation & report generation) |
| File Storage | **MinIO** (S3-compatible, local Docker) |
| CV Parsing | `pypdf`, `python-docx`, `beautifulsoup4` |
| PDF Generation | `reportlab` |
| Speech-to-Text | **Whisper** (local, via `faster-whisper`) |
| Text-to-Speech | **TTS service** (streaming via WebSocket binary frames) |
| Auth | JWT (`python-jose`) + `passlib[bcrypt]` |

### Frontend
| Layer | Technology |
|---|---|
| Framework | **Next.js 14.2.3** (App Router, TypeScript) |
| Styling | **Tailwind CSS** v3 |
| Charts | **Chart.js** + `react-chartjs-2`, **Recharts** |
| Icons | `lucide-react` |

---

## 📁 Full Directory Structure

```
implementation/
├── .env                          ← Environment variables (DO NOT COMMIT)
├── .env.example                  ← Template for environment variables
├── docker-compose.yml            ← Full infra: postgres, qdrant, redis, minio, backend, frontend
├── Makefile                      ← Convenience commands
├── backend/
│   ├── app/
│   │   ├── main.py               ← FastAPI app + CORS + router registration
│   │   ├── celery_app.py         ← Celery instance configuration
│   │   ├── agents/               ← 6 LangGraph agents (see AGENTS.md)
│   │   ├── api/                  ← FastAPI routers (REST + WebSocket)
│   │   ├── core/                 ← Config, security
│   │   ├── db/                   ← SQLAlchemy base, session factory
│   │   ├── models/
│   │   │   ├── orm.py            ← SQLAlchemy ORM models
│   │   │   └── schemas.py        ← Pydantic request/response schemas
│   │   ├── services/             ← Business logic services
│   │   └── tasks/                ← Celery async tasks
│   ├── alembic/                  ← DB migrations
│   ├── scripts/
│   │   └── load_kaggle_data.py   ← Seeds 2,292 questions into Qdrant
│   ├── seed_questions.py         ← Alternative seed script
│   ├── requirements.txt
│   └── langgraph.json            ← LangGraph Studio config (6 agents)
├── frontend/
│   ├── app/
│   │   ├── page.tsx              ← Login/Landing page
│   │   ├── layout.tsx            ← Root layout
│   │   ├── dashboard/page.tsx    ← Main dashboard
│   │   ├── profile/              ← CV upload + analysis page
│   │   ├── session/              ← Interview session page (WebSocket)
│   │   └── results/              ← Report results page
│   ├── components/
│   │   ├── MatchDashboard.tsx    ← CV ↔ JD match analysis component
│   │   ├── DurationPicker.tsx    ← Interview duration selector
│   │   └── ui/                   ← Button, Card, Input shared components
│   └── lib/
│       ├── api.ts                ← Axios API client (uses cookie auth)
│       └── auth.tsx              ← Auth context (useAuth hook, JWT)
└── models/                       ← Whisper model files (local, not in git)
```

---

## 🌐 API Routers (registered in `main.py`)

| Prefix | File | Description |
|---|---|---|
| `/auth` | `api/auth.py` | Login, register, `/auth/me` |
| `/sessions` | `api/sessions.py` | Create/list/get sessions |
| `/ws` | `api/websocket.py` | WebSocket interview endpoint |
| `/dashboard` | `api/dashboard.py` | Stats, score evolution, strengths profile |
| `/tools` | `api/tools.py` | CV analysis, match analysis tools |
| (none) | `api/resumes.py` | Resume CRUD + analysis |
| (none) | `api/exchanges.py` | Exchange retrieval |
| (none) | `api/evaluations.py` | Evaluation retrieval |
| (none) | `api/reports.py` | Report retrieval |
| (none) | `api/profiles.py` | Candidate profile CRUD (legacy) |

---

## 🔑 Environment Variables (`.env`)

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/interviewai

# LLM
GROQ_API_KEY=gsk_...          # Required for Llama 3.3 + nomic embeddings
LANGCHAIN_API_KEY=ls__...     # LangSmith tracing

# Storage
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...

# Redis / Celery
REDIS_URL=redis://redis:6379/0

# Qdrant
QDRANT_HOST=qdrant
QDRANT_HTTP_PORT=6333

# Auth
SECRET_KEY=...                # JWT secret
```

---

## 🚀 How to Run

```bash
# Start all services
docker-compose up --build

# Seed Qdrant with 2,292 interview questions from Kaggle datasets
docker exec local_backend python scripts/load_kaggle_data.py

# Run LangGraph Studio (for agent visualization)
cd backend && langgraph dev --host 127.0.0.1 --port 2024

# Frontend dev server
cd frontend && npm run dev
```

- **Backend API:** `http://localhost:8000`
- **Frontend:** `http://localhost:3000`
- **LangGraph Studio:** `http://127.0.0.1:2024`
- **Qdrant Dashboard:** `http://localhost:6333/dashboard`
- **MinIO Console:** `http://localhost:9001`
