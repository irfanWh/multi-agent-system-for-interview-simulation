# InterviewAI — Frontend Architecture

> Read `CONTEXT.md` first. All frontend code is in `frontend/`.

---

## Tech Stack
- **Framework:** Next.js 14.2.3 (App Router, TypeScript)
- **Styling:** Tailwind CSS v3 — dark theme, colors based on `slate-*`, `indigo-*`, `purple-*`
- **Charts:** `Chart.js` + `react-chartjs-2` (Line + Radar charts on dashboard), `Recharts` (available but not primary)
- **Icons:** `lucide-react`
- **Auth:** JWT stored in `localStorage` under key `"token"`. Auth context in `lib/auth.tsx`.
- **API Client:** Custom fetch wrapper in `lib/api.ts`. Base URL: `process.env.NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`)

---

## Auth Flow

`lib/auth.tsx` exports:
- `AuthProvider` — wraps the app in `app/layout.tsx`
- `useAuth()` — returns `{ user, loading, login, logout }`

On load: reads `localStorage.getItem('token')` → calls `GET /auth/me` → sets user state.  
On 401: removes token from localStorage, redirects to `/`.  
After login: `login(token)` stores token and calls `fetchUser()`.

---

## Pages Map

| Route | File | Description |
|---|---|---|
| `/` | `app/page.tsx` | Login + Register landing page |
| `/dashboard` | `app/dashboard/page.tsx` | Main dashboard with stats, charts, session history |
| `/session/new` | `app/session/new/page.tsx` | 3-step wizard to configure and launch a new interview |
| `/session/[id]` | `app/session/[id]/page.tsx` | Live interview WebSocket session page |
| `/results/[id]` | `app/results/[id]/page.tsx` | Final report results page after session ends |
| `/profile` | `app/profile/page.tsx` | Candidate profile page |

---

## Dashboard (`app/dashboard/page.tsx`)

Fetches in parallel on mount:
```ts
const [sessionsRes, statsRes] = await Promise.all([
  api.get('/sessions/'),
  api.getDashboardStats()
]);
```

### Stats Cards (from `GET /dashboard/stats`):
- `total_interviews`, `completed_interviews`, `active_interviews`, `active_resumes`
- `average_score`, `best_score`

### Charts:
1. **Score Evolution (Line Chart)** — uses `stats.score_evolution: [{date, score}]` from backend
2. **Strengths Profile (Radar Chart)** — uses `stats.strengths_profile: [{category, score}]` from backend
   - ⚠️ **Known Issue:** The Strengths Profile radar chart will be empty until the user has at least one completed session with a generated report. The backend derives it from `Report.competency_breakdown` JSONB.
   - `competency_breakdown` is populated by the Report Generator agent as `{category_name: {score, insights}}`

### Session List:
- Sorted by `started_at` descending
- Displays: interview type badge, status badge, job description preview, date

---

## Session Creation Wizard (`app/session/new/page.tsx`)

**3-step wizard:**

### Step 1 — Resume Selection
- Calls `GET /resumes` to list existing CVs
- File upload → `POST /resumes/upload` (multipart)
- After upload, polls `GET /resumes/{id}/status` every 2s (max 90 attempts = 3 min) until `is_analyzed == true`
- Delete resume with confirmation modal → `DELETE /resumes/{id}`

### Step 2 — Job Description
- Two modes: **Paste Text** or **Provide URL**
- URL mode → `POST /tools/extract-job-url` → extracts text from LinkedIn/Indeed/etc.
- Client-side JD validation (minimum words, keyword check)
- Match Analysis → `POST /resumes/{resumeId}/match-analysis` → shows `MatchDashboard` component

### Step 3 — Interview Configuration
- Interview type: `technical | behavioral | mixed`
- Duration: 5–120 minutes via `DurationPicker` component (steps of 5)
- Launch → `POST /sessions/?duration_minutes={n}` with body `{resume_id, job_description, interview_type}`
- On success → redirect to `/session/{session_id}`

---

## Live Interview Page (`app/session/[id]/page.tsx`)

Connects to WebSocket: `ws://localhost:8000/ws/session/{id}`

### WebSocket Protocol:

**On connect — client sends:**
```json
{"type": "session_start", "mode": "text"}
```
(or `"mode": "voice"` for voice mode)

**Messages FROM server (incoming):**
| type | Payload | Action |
|---|---|---|
| `question` | `{text, anchor_title}` | Display the question text in chat |
| `tts_start` | `{text}` | TTS audio is starting |
| binary bytes | audio chunks (voice mode) | Play audio |
| `tts_end` | — | Unmute mic |
| `interviewer_thinking` | — | Show loading spinner |
| `transcript` | `{text, is_final}` | Show live STT transcription |
| `anchor_change` | `{anchor_title}` | Update topic indicator |
| `session_complete` | `{message}` | Show closing message, redirect to results |
| `error` | `{message}` | Show error |

**Messages TO server (outgoing — text mode):**
```json
{"type": "answer", "text": "candidate's typed answer"}
```

**Binary frames (voice mode):**
- Outgoing: raw PCM/WebM audio chunks (16kHz recommended)
- Incoming: `0x01` prefix + MP3/audio chunks for TTS playback

---

## API Client (`lib/api.ts`)

```ts
// Base configuration
API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'
WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws'

// Auth: Bearer token from localStorage
// 401 → auto logout + redirect to /
```

### Available methods:
```ts
api.get(path)
api.post(path, body)
api.login(formData)          // OAuth2PasswordRequestForm
api.register(data)
api.getMe()                   // GET /auth/me
api.uploadCV(file, role, level, jobText?, jobUrl?)
api.createSession(data)       // POST /sessions/
api.getSession(id)
api.getExchanges(id)
api.getReport(sessionId)
api.generateReport(sessionId)
api.getEvaluations(sessionId)
api.getDashboardStats()       // GET /dashboard/stats
```

---

## Key Components

### `MatchDashboard` (`components/MatchDashboard.tsx`)
Displays the match analysis report with:
- Overall fit score (large percentage)
- Matched skills (green badges)
- Missing skills (red badges)
- Critical gaps list
- Recommended focus areas
- Button to proceed to interview setup

Props:
```ts
{
  matchReport: MatchReport,
  wasCached: boolean,
  onStartInterview: (focusAreas: string[]) => void
}
```

### `DurationPicker` (`components/DurationPicker.tsx`)
A circular knob/slider for picking interview duration (5–120 min, step 5).

---

## Design System

The app uses a **dark glassmorphism** style:
- Background: `bg-[#0a0a0f]` (near-black)
- Cards: `bg-slate-900/40 backdrop-blur-xl border border-white/10`
- Primary accent: `indigo-500` / `indigo-400`
- Secondary accent: `purple-500` / `fuchsia-600`
- Success: `emerald-400`
- Warning: `amber-400`
- Error: `red-400`
- Text primary: `slate-100`
- Text secondary: `slate-400`
- Glow effects: `shadow-[0_0_20px_rgba(99,102,241,0.4)]`
- Animations: `animate-in fade-in`, `slide-in-from-*`, `animate-spin`
