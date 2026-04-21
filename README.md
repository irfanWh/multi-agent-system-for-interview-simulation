# InterviewAI

![InterviewAI Architecture](https://img.shields.io/badge/Status-Active-success)

## 📌 Context
Technical interviewing is an expensive and time-consuming process for both companies and candidates. Screening countless profiles and scheduling initial technical discussions requires significant human intervention, often leading to bottlenecks in the recruitment pipeline.

## ⚠️ Problem
- **High cost of manual screening:** HR and technical leads spend countless hours evaluating candidate skills.
- **Lack of standardization:** Initial interviews can be subjective and vary significantly between interviewers.
- **Scheduling friction:** Organizing technical screening tests across different time zones slows down hiring.

## 💡 Solution
**InterviewAI** is an autonomous, multi-agent AI system designed to conduct highly realistic technical and behavioral interviews in real-time. It analyzes a candidate's CV, dynamically generates personalized evaluation criteria, and conducts a live conversational interview (via Text or Audio) to assess the candidate's skills, eventually outputting a detailed performance report.

## 🚀 Tech Stack
### **Frontend**
- **Next.js 14** (App Router, React)
- **TypeScript** & **Tailwind CSS**
- **WebSockets** (Real-time live chat & audio streaming)

### **Backend**
- **FastAPI** (Python 3.12, Async)
- **LangGraph & LangChain** (Multi-Agent Orchestration workflow)
- **PostgreSQL & Redis** (State management & Celery queues)
- **Qdrant** (Vector Database for RAG and semantic question matching)
- **MinIO** (S3-compatible Object Storage for CVs and PDF reports)

### **AI Services**
- **Groq API** (Ultra-fast LLM inference)
- **Faster-Whisper** (Local, highly optimized Speech-To-Text pipeline)
- **Coqui-TTS** (Local Text-To-Speech engine)

## 🏗 Architecture (Agents Flow)
The application leverages a robust **Multi-Agent System** architecture managed by **LangGraph**:
1. **Agent 1 (Profile Analyzer):** Extracts skills, gaps, and calibrated levels directly from the uploaded CV PDF.
2. **Agent 2 (Orchestrator):** Interacts with Qdrant to pull relevant technical questions and builds a dynamic `SessionPlan` customized for the candidate's exact profile.
3. **Agent 3 (Interviewer):** The stateful live agent. Connects via WebSockets to conduct the interview, asking questions, actively listening to the candidate, detecting incomplete answers, and dynamically generating relevant follow-ups.
4. **Agent 4 (Evaluator/Reporter):** Generates a comprehensive PDF grading report based on the candidate's responses across the session.

## ⚙️ How to Run It

1. **Clone the repository**
   ```bash
   git clone https://github.com/irfanWh/multi-agent-system-for-interview-simulation.git
   cd multi-agent-system-for-interview-simulation
   ```

2. **Setup Environment Variables**
   Create a `.env` file at the root of the project by copying the example:
   ```bash
   cp .env.example .env
   # Make sure to add your Groq API Key and adjust ports if necessary
   ```

3. **Start the Infrastructure via Docker**
   The entire infrastructure is containerized. Start the stack:
   ```bash
   docker-compose up -d
   ```
   > Note: On the first run, downloading the AI models (Whisper, TTS) and installing dependencies might take a few minutes.

4. **Access the Applications**
   - **Frontend UI:** [http://localhost:3000](http://localhost:3000)
   - **API Swagger/Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **PgAdmin:** [http://localhost:5050](http://localhost:5050)
   - **MinIO Console:** [http://localhost:9001](http://localhost:9001)

## 📄 Resume
InterviewAI revolutionizes the initial candidate screening barrier. By leveraging local lightweight LLM & audio models combined with the blazing speed of Groq APIs, the project ensures data privacy while completely replicating the natural pacing, follow-up intuition, and criteria-based scoring of a human Technical Lead.
