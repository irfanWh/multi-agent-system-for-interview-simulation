# InterviewAI — Complete API Reference

> Read `CONTEXT.md` first. All routes are defined in `backend/app/api/`.

---

## Authentication

All endpoints except `/auth/login` and `/auth/register` require:
```
Authorization: Bearer <jwt_token>
```

JWT is signed with `SECRET_KEY` from `.env`, algorithm HS256.

---

## Auth Endpoints (`/auth`)

### `POST /auth/register`
Create a new user.
```json
// Body
{"email": "user@example.com", "password": "secret123"}

// Response 201
{"id": "uuid", "email": "user@example.com", "created_at": "...", "updated_at": "..."}
```

### `POST /auth/login`
OAuth2 form login.
```
Content-Type: application/x-www-form-urlencoded
Body: username=user@example.com&password=secret123
```
```json
// Response 200
{"access_token": "jwt...", "token_type": "bearer"}
```

### `GET /auth/me`
Returns current user info from JWT.
```json
// Response 200
{"id": "uuid", "email": "user@example.com", "created_at": "...", "updated_at": "..."}
```

---

## Resume Endpoints

### `POST /resumes/upload`
Upload a CV (PDF, DOCX, or TXT). Triggers async Profile Analysis (Celery).
```
Content-Type: multipart/form-data
Body: file=<binary>
```
```json
// Response 200
{
  "resume_id": "uuid",
  "is_analyzed": false,
  "was_duplicate": false
}
```
- If the file hash already exists for this user, returns `was_duplicate: true` and the existing `resume_id`.
- Profile analysis runs in background. Poll `/resumes/{id}/status` to wait.

### `GET /resumes`
List all resumes for the current user.
```json
// Response 200
[
  {
    "id": "uuid",
    "filename": "my_cv.pdf",
    "created_at": "...",
    "is_analyzed": true,
    "sessions_count": 3
  }
]
```

### `GET /resumes/{id}/status`
Poll resume analysis status.
```json
// Response 200
{"is_analyzed": true}
```

### `DELETE /resumes/{id}`
Delete a resume and all its associated sessions, exchanges, evaluations, and reports (cascade).

### `POST /resumes/{id}/match-analysis`
Run or retrieve cached Match Analyzer.
```json
// Body
{"job_description": "We are looking for a Senior React Developer..."}

// Response 200
{
  "match_report": {
    "overall_fit_score": 78,
    "matched_skills": ["React", "TypeScript"],
    "missing_skills": ["GraphQL", "AWS"],
    "critical_gaps": ["No cloud deployment experience"],
    "overqualified_areas": [],
    "recommended_focus_areas": ["AWS", "GraphQL"]
  },
  "was_cached": false
}
```

---

## Session Endpoints (`/sessions`)

### `POST /sessions/?duration_minutes={n}`
Create a new interview session. This is the **main pipeline trigger**:
1. Validates resume is analyzed
2. Optionally runs Match Analyzer (if JD provided)
3. Runs Interview Planner agent
4. Runs Orchestrator agent (Qdrant enrichment)
5. Saves session with `session_plan` to DB

```json
// Body
{
  "resume_id": "uuid",
  "job_description": "optional JD text",
  "interview_type": "technical",   // "technical" | "behavioral" | "mixed"
  "status": "pending"
}

// Query param: ?duration_minutes=30

// Response 201
{
  "id": "uuid",
  "user_id": "uuid",
  "resume_id": "uuid",
  "interview_type": "technical",
  "status": "pending",
  "session_plan": { ... },
  "job_description": "...",
  "started_at": null,
  "ended_at": null
}
```

### `GET /sessions/`
List all sessions for current user (paginated with `skip` + `limit`).

### `GET /sessions/{id}`
Get a single session with its plan.

### `PATCH /sessions/{id}/status`
Update session status or timestamps.
```json
// Body
{"status": "active", "started_at": "2024-01-01T00:00:00Z"}
```

### `GET /sessions/{id}/exchanges`
Get all Q&A exchanges for a session.

### `GET /sessions/{id}/evaluations`
Get all evaluations for a session's exchanges.

### `GET /sessions/{id}/report`
Get the generated report for a session.

---

## WebSocket Endpoint

### `WS /ws/session/{session_id}`

Runs the live Interviewer (ReAct) agent.

**Connection flow:**
1. Client connects
2. Server validates session exists and has a `session_plan`
3. Client sends: `{"type": "session_start", "mode": "text"}` (or `"voice"`)
4. Interview begins

**Server → Client messages:**
```json
{"type": "question", "text": "...", "anchor_title": "..."}
{"type": "tts_start", "text": "..."}      // voice mode only
{"type": "tts_end"}                        // voice mode only
{"type": "interviewer_thinking"}
{"type": "transcript", "text": "...", "is_final": true}  // voice mode only
{"type": "anchor_change", "anchor_title": "..."}
{"type": "session_complete", "message": "..."}
{"type": "error", "message": "..."}
```
Binary frames from server: `0x01` prefix + audio chunk (TTS, voice mode)

**Client → Server messages:**
```json
{"type": "answer", "text": "candidate's typed answer"}
```
Binary frames to server: raw audio PCM (voice mode)

---

## Dashboard Endpoints (`/dashboard`)

### `GET /dashboard/stats`
Returns aggregated statistics for the current user.

```json
// Response 200
{
  "total_interviews": 12,
  "completed_interviews": 8,
  "active_interviews": 1,
  "active_resumes": 3,
  "average_score": 7.2,
  "best_score": 9.1,
  "score_evolution": [
    {"date": "Jan 15", "score": 6.5},
    {"date": "Feb 02", "score": 7.8}
  ],
  "strengths_profile": [
    {"category": "Python", "score": 8.5},
    {"category": "System Design", "score": 6.0},
    {"category": "Communication", "score": 7.5}
  ]
}
```

> **Note:** `strengths_profile` is derived from `Report.competency_breakdown` averaged across all reports. It will be empty if no reports exist.

---

## Tools Endpoints (`/tools`)

### `POST /tools/extract-job-url`
Scrape a job posting URL and extract the job description text.

```json
// Body
{"url": "https://www.linkedin.com/jobs/view/12345"}

// Response 200
{
  "extracted_text": "Title: Senior React Developer\nURL: ...\n\n...",
  "source_url": "https://..."
}
```
- Handles LinkedIn URL rewrites (e.g. `currentJobId=` param)
- Returns 422 if LinkedIn blocks scraping (auth wall) — user must paste manually
- Runs through same JD validation as the manual paste flow
