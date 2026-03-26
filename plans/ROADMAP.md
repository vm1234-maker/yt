# NemoClaw YouTube Automation — Implementation Roadmap

> Full-stack AI agent system: Next.js 16 dashboard + FastAPI backend + Supabase + NemoClaw manager

---

## What Was Built

A fully automated YouTube ambient/soundscape channel pipeline with:
- A dark command-center dashboard (Next.js 16) with live Realtime updates
- A Python backend (FastAPI + Celery) executing 6 AI agents
- Supabase as the database, Realtime layer, and video/thumbnail storage
- OpenAI handling all AI generation (text, images, research)
- Static CC0 audio and video loops assembled by FFmpeg
- YouTube Data API for uploads, YouTube Analytics API for performance tracking
- NemoClaw autonomous manager sending iMessage notifications and daily summaries

---

## Architecture

```
NemoClaw (autonomous manager — runs on Mac)
  - Reads analytics from Supabase
  - Triggers agent runs via Next.js API
  - Sends iMessage daily summary at 8am
  - Auto-approves content that passes quality checks
  - Sends iMessage with dashboard link for borderline approvals
        ↓
Next.js 16 Dashboard (localhost:3000 / Vercel)
  - app/api/** routes proxy to FastAPI
  - Server Components read Supabase directly (supabase-admin.ts)
  - Client Components subscribe to Supabase Realtime (supabase.ts)
        ↓
FastAPI + Celery Backend (Docker / Railway)
  - POST /api/run-agent  → writes 'running' row, enqueues Celery task
  - GET  /api/agents     → latest run per agent from Supabase
  - GET  /api/agent-status/{id} → single run status
  - Celery workers execute agent functions
  - Celery Beat schedules daily analytics (4am) + NemoClaw summary (8am)
        ↓
6 Agent Functions (backend/agents/)
  ├── Research Agent   — OpenAI web search + YouTube Data API
  ├── Content Agent    — GPT-4.1 (text) + gpt-image-1 (thumbnails)
  ├── Production Agent — gpt-image-1 + static loops + FFmpeg
  ├── Upload Agent     — YouTube Data API v3 (OAuth2)
  ├── Analytics Agent  — YouTube Analytics API
  └── Strategy Agent   — GPT-4.1 ROI loop → triggers Content Agent
        ↓
Supabase (Postgres + Realtime + Storage)
  - Tables: agent_runs, content_queue, video_analytics, channel_metrics
  - Storage buckets: videos, thumbnails
  - Realtime: agent_runs and content_queue have live subscriptions
        ↓
Static Asset Libraries (local, one-time download)
  - backend/visuals/ — 13 CC0 looping MP4s (one per niche)
  - backend/audio/   — 13 CC0 audio loops from Freesound.org (one per niche)
```

---

## Credentials in Use

All secrets live in two files — never committed.

### `backend/.env` (Python backend)

| Key | Service | Status |
|---|---|---|
| `SUPABASE_URL` | Supabase | Set |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase | Set |
| `UPSTASH_REDIS_REST_URL` | Upstash | Set |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash | Set |
| `OPENAI_API_KEY` | OpenAI | Set |
| `YOUTUBE_API_KEY` | Google Cloud | Set |
| `YOUTUBE_CLIENT_ID` | Google Cloud OAuth2 | Set |
| `YOUTUBE_CLIENT_SECRET` | Google Cloud OAuth2 | Set |
| `YOUTUBE_REFRESH_TOKEN` | Generated via youtube_auth.py | Set |
| `IMESSAGE_RECIPIENT` | Your phone number (+1XXXXXXXXXX) | Set |
| `NEXT_PUBLIC_APP_URL` | http://localhost:3000 | Set |

### `.env.local` (Next.js frontend)

| Key | Service | Status |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase | Set |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase | Set |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase | Set |
| `BACKEND_URL` | http://localhost:8000 | Set |

---

## Tech Stack (Actual)

### Frontend
- Next.js 16 (App Router, Turbopack)
- TypeScript strict mode
- Tailwind CSS v4
- lucide-react (icons)
- recharts (analytics charts)
- @supabase/supabase-js (data + Realtime)
- Zod (API route validation)

### Backend
- FastAPI + Uvicorn
- Celery 5.4 + Celery Beat
- Upstash Redis (broker + result backend, `rediss://` with `ssl_cert_reqs=CERT_NONE`)
- Supabase Python client
- google-api-python-client (YouTube Data + Analytics APIs)
- google-auth-oauthlib (OAuth2 for upload/analytics)
- openai >= 1.70.0 (GPT-4.1 text + gpt-image-1 + gpt-4o-search-preview)
- httpx (async HTTP for all external calls)
- pydantic-settings (env var management)
- macpymessenger (iMessage notifications on macOS)
- FFmpeg (installed in Docker container via apt)

### Infrastructure
- Docker + docker-compose (api + worker + beat services)
- Supabase (Postgres, Realtime, Storage)
- Upstash Redis (free tier, ~10k req/day)
- Vercel (Next.js — pending deployment)
- Railway or Render (FastAPI — pending deployment)

---

## Phase 1 — Supabase Schema + Live Reads ✅

**What was done:**
- Created 4 tables: `agent_runs`, `content_queue`, `video_analytics`, `channel_metrics`
- Applied migration via Supabase MCP
- Enabled Realtime on `agent_runs` and `content_queue`
- Created `lib/supabase.ts` (anon key — client-side) and `lib/supabase-admin.ts` (service role — server-only)
- All 4 pages converted from hardcoded mock data to async Supabase reads
- `components/activity-feed.tsx` — live Realtime INSERT subscription
- `components/content-actions.tsx` + `app/content/actions.ts` — approve/reject Server Actions
- `components/analytics-charts.tsx` — data-driven with empty states

**Key fix applied:** `lib/supabase.ts` and `lib/supabase-admin.ts` are split into separate files. Client components only import from `supabase.ts` (anon key). Server Components and API routes only import from `supabase-admin.ts` (service role). This prevents `SUPABASE_SERVICE_ROLE_KEY` from leaking to the browser bundle.

---

## Phase 2 — FastAPI + Celery Backend ✅

**What was done:**
- FastAPI app with `/health`, `/api/run-agent`, `/api/agent-status/{id}`, `/api/agents`
- Celery worker connected to Upstash Redis (`rediss://` URL with `?ssl_cert_reqs=CERT_NONE`)
- Celery Beat schedule: analytics at 4am, NemoClaw summary at 8am
- `backend/tools/supabase_tool.py` — shared DB read/write/log helper for all agents
- Next.js API routes: `run-agent`, `agent-status/[id]`, `agents`
- `components/run-agent-button.tsx` — client component triggering agent runs
- `backend/docker-compose.yml` — api + worker + beat, `./sandbox/output` mounted for FFmpeg output

**Key fix applied:** Upstash Redis requires `?ssl_cert_reqs=CERT_NONE` appended to the `rediss://` broker URL for Celery 5.4+.

---

## Phase 3 — Agent Implementations ✅

All 6 agents are fully implemented as plain Python functions (no CrewAI orchestration).

### Research Agent (`backend/agents/research.py`)
- Uses `OpenAITool.research()` with `gpt-4o-search-preview` for a single batch Perplexity-style query covering all 12 niches
- Cross-checks competition with YouTube Data API (free, quota-based)
- Scores niches by RPM estimate, competition level, and trend direction
- Outputs ranked niche report to `agent_runs.full_output`

### Content Agent (`backend/agents/content.py`)
- Uses `GPT-4.1` to generate 3 title variants, select best, write description and 15 tags
- Uses `gpt-image-1` to generate a 1792×1024 16:9 thumbnail
- Uploads thumbnail bytes to Supabase Storage → stores URL in `content_queue`
- Creates `content_queue` row with status `awaiting_approval`

### Production Agent (`backend/agents/production.py`)
- Generates thumbnail with `gpt-image-1` (if not already set by Content Agent)
- Looks up static CC0 visual loop from `backend/visuals/` by niche name
- Looks up static CC0 audio loop from `backend/audio/` by niche name
- FFmpeg renders: `-stream_loop -1` on both inputs, `-t` sets exact duration, no `-shortest`
- Uploads MP4 to Supabase Storage `videos` bucket
- Updates `content_queue` with `video_url`, `audio_url`, `thumbnail_url`, status `approved`

### Upload Agent (`backend/agents/upload.py`)
- Downloads video from Supabase Storage URL to `/tmp/`
- Resumable YouTube upload via `MediaFileUpload` with 50MB chunks
- Sets title, description, tags (max 15), category 10 (Music)
- Sets privacy to `private` + `publishAt` for scheduled uploads, `public` for immediate
- Sets thumbnail via `thumbnails().set()`
- Updates `content_queue` with `youtube_video_id` and status `scheduled` or `uploaded`

### Analytics Agent (`backend/agents/analytics.py`)
- Fetches per-video metrics from YouTube Analytics API for all uploaded/scheduled videos
- Derives RPM: `revenue / (watch_time_minutes / 60) * 1000`
- Inserts rows into `video_analytics`
- Fetches channel-level 7-day rollup → inserts into `channel_metrics`
- Scheduled via Celery Beat at 4am daily

### Strategy Agent (`backend/agents/strategy.py`)
- Reads `video_analytics`, `channel_metrics`, latest research run from Supabase
- Groups videos by niche, computes retention at 30min and 10min
- Applies exploit/test/kill rules (thresholds: 40% @ 30min = proven, <20% @ 10min after 5 uploads = dead)
- Uses `GPT-4.1` to pick the single best niche + angle for next video
- Triggers Content Agent via `httpx.post` to `NEXT_PUBLIC_APP_URL/api/run-agent`

---

## Phase 4 — Real-time Dashboard ✅

| Component | Mechanism |
|---|---|
| `components/agent-status-grid.tsx` | Realtime `*` on `agent_runs` — live status badges + progress bars |
| `components/live-agent-card.tsx` | Realtime UPDATE on specific `run.id` + 5s polling fallback |
| `components/content-queue-table.tsx` | Realtime `*` on `content_queue` — INSERT/UPDATE/DELETE |
| `components/nav.tsx` | Fetches `/api/agents` on mount + Realtime `*` on `agent_runs` for sidebar dots |
| `app/dashboard/page.tsx` | Server Component passes initial runs to `AgentStatusGrid` + `ActivityFeed` |
| `app/agents/page.tsx` | Computes per-agent stats server-side, passes to `LiveAgentCard` |
| `app/content/page.tsx` | Passes initial queue to `ContentQueueTable` |

---

## Phase 5 — NemoClaw + iMessage ✅

**What was built** (tools created, OpenClaw deployment is a manual step):

```
nemoclaw/
  agent-instructions.md        # OpenClaw system prompt — identity, daily routine, approval rules
  openclaw-sandbox.yaml        # Network policy — allowlisted endpoints only
  tools/
    send_imessage.py           # AppleScript iMessage via osascript (fallback)
    read_analytics.py          # Reads Supabase tables by type
    trigger_agent.py           # POST to /api/run-agent
    approve_content.py         # approve/reject content_queue rows + sends iMessage
    update_strategy.py         # Writes nemoclaw_notes rows for Strategy Agent
```

**iMessage daily summary** runs via Celery Beat at 8am — reads Supabase, builds a plain-text report, sends to `IMESSAGE_RECIPIENT`.

**Approval flow**: NemoClaw sends an iMessage with a link to `http://localhost:3000/content`. Human approves/rejects via the dashboard `ContentActions` buttons (Server Actions).

**Note**: `app/api/telegram-webhook/route.ts` was removed. The Telegram-based button approval flow was not implemented.

---

## Static Asset Setup (one-time manual step)

### `backend/visuals/` — looping ambient MP4s

Download 13 files from [Pixabay](https://pixabay.com/videos/) or [Pexels](https://www.pexels.com/videos/) (CC0 license):

```
rain_sounds.mp4, lofi_study_music.mp4, dark_forest_ambiance.mp4,
coffee_shop_ambiance.mp4, fireplace_crackle.mp4, thunderstorm_sounds.mp4,
binaural_beats.mp4, sleep_sounds_anxiety.mp4, nature_asmr.mp4,
white_noise.mp4, ocean_waves_sleep.mp4, forest_birds_morning.mp4,
default.mp4
```

See `backend/visuals/README.md` for exact search terms.

### `backend/audio/` — looping ambient MP3s

Download 13 files from [Freesound.org](https://freesound.org) (CC0 license):

```
rain_sounds.mp3, lofi_study_music.mp3, dark_forest_ambiance.mp3,
coffee_shop_ambiance.mp3, fireplace_crackle.mp3, thunderstorm_sounds.mp3,
binaural_beats.mp3, sleep_sounds_anxiety.mp3, nature_asmr.mp3,
white_noise.mp3, ocean_waves_sleep.mp3, forest_birds_morning.mp3,
default.mp3
```

See `backend/audio/README.md` for exact search terms and quality requirements.

---

## Running the System

### Start backend (runs in background)
```bash
cd backend
docker compose up -d
```

### Stop backend
```bash
cd backend
docker compose down
```

### View backend logs
```bash
cd backend
docker compose logs -f
```

### Start dashboard
```bash
npm run dev
# Open http://localhost:3000
```

### Rebuild after code changes
```bash
cd backend
docker compose up -d --build
```

---

## Deployment Plan (pending)

| Service | Platform | Status |
|---|---|---|
| Next.js dashboard | Vercel | Not yet deployed |
| FastAPI + Celery | Railway or Render | Not yet deployed |
| Redis | Upstash | Live (free tier) |
| Database + Storage | Supabase | Live |
| iMessage notifications | Mac only | Works locally, not deployable to Linux |

**iMessage limitation**: `macpymessenger` and AppleScript require macOS + Messages.app. If deploying the Celery worker to Railway/Render (Linux), the iMessage step will silently fail. Either keep the worker local on Mac, or switch to a cross-platform notification service (Pushover, ntfy, etc.) for production deployment.

---

## Business Rules (Strategy Agent)

- RPM targets: `$8–$12` for sleep/ambient, `$10–$15` for study/focus
- Watch time is the primary optimization signal
- Video lengths: 1h minimum, 3h standard, 8h for sleep content
- A niche is "proven" after 3 uploads averaging >40% retention at 30 minutes
- A niche is "dead" after 5 uploads averaging <20% retention at 10 minutes
- Never upload more than 7 videos in a week without NemoClaw asking for approval
- Audio must be CC0 licensed — no stock music libraries
- Upload schedule: 3–5 videos per week to start

---

## Known Issues / Deferred

- **CrewAI installed but unused** — `crew.py` exists as a scaffold, nothing calls it. Can be removed to reduce Docker image size (~50MB).
- **iMessage not cross-platform** — works locally on Mac, will not work on Linux deployment.
- **NemoClaw OpenClaw deployment** — `nemoclaw/` tools are ready but the OpenClaw agent itself requires a NemoClaw account and manual `nemoclaw onboard` setup.
- **Supabase Storage buckets** — `videos` and `thumbnails` buckets need to be created manually in the Supabase dashboard before the Production Agent runs.
