# InterviewAI Project Context — Memory File

## 🚀 Project Overview
**InterviewAI** is a multi-agent system designed to simulate end-to-end technical interviews. It orchestrates multiple LLM-based agents to parse CVs, generate tailored interview plans, conduct real-time simulations, and provide detailed evaluations.

## 🏗️ Architecture Overview
- **Backend**: FastAPI (Python 3.12)
- **Agent Orchestration**: LangGraph (StateGraph)
- **LLM**: Groq API (Llama 3.3 70B Versatile)
- **Vector DB**: Qdrant (for RAG — question bank and memory)
- **Primary DB**: PostgreSQL (SQLAlchemy + Alembic)
- **Parsing**: `pypdf` and `python-docx` for CV ingestion.
- **Infrastructure**: Fully containerized (14 containers including Redis, MinIO, Celery, Whisper, TTS).

## 📁 Key Files & Modules
- `backend/app/main.py`: Entry point, lifecycle management (VDB init).
- `backend/app/services/qdrant_service.py`: Singleton for VDB operations, embeddings, and semantic search.
- `backend/app/agents/profile_analyzer.py`: **Agent 1**. Uses a 3-node graph to parse CVs and calibrate candidate levels.
- `backend/app/agents/orchestrator.py`: **Agent 2 (Planning Phase)**. Will generate interview sessions.
- `backend/app/api/profiles.py`: CV upload and analysis endpoints.
- `backend/seed_questions.py`: Script to populate the VDB with technical and behavioral questions.

## 📈 Current Progress
- ✅ **Infrastructure**: All containers are healthy and reachable.
- ✅ **Vector Database**: Qdrant initialized and seeded with 20 initial questions.
- ✅ **Auth**: User registration and login flow functional.
- ✅ **CV Parser**: Successfully extracting text from PDF/DOCX.
- ✅ **Agent 1 (Profile Analyzer)**: Fully functional. Correctly extracts skills and detects gaps via Groq.
- 🚧 **Agent 2 (Orchestrator)**: Design phase. Schema defined, logic mapped out.
- ⏳ **WebSocket Integration**: Next major infrastructure step for real-time interaction.

## 🛠️ Problems Solved
- **Dependency Conflicts**: Fixed a major crash related to Pydantic v1 vs v2 by upgrading the entire LangChain/LangGraph stack.
- **LLM Deprecation**: Migrated from the decommissioned `llama-3.1` to `llama-3.3-70b-versatile` on Groq.
- **VDB Optimization**: Upgraded `qdrant-client` to resolve a critical `pytest` import error that was stalling backend health checks.
- **Graph State Contract**: Fixed `InvalidUpdateError` in LangGraph by ensuring nodes always return a non-empty state update.

## 💡 Important Decisions
- **RAG-First Strategy**: Using semantic search via `nomic-embed-text` to ensure interview questions are grounded in real data rather than purely halluncinated.
- **LangGraph over LCEL**: Chose StateGraph for its robustness in handling complex, cyclic agentic workflows.
- **Structured Output**: Using Pydantic models with `.with_structured_output()` for reliable JSON extraction from LLMs.
- **Fallback Embeddings**: Using a deterministic SHA-512 hash fallback for embeddings to allow the system to remain partially functional even if the Groq API fails.

---
*Created on 2026-04-10. Update this file as the project evolves.*
