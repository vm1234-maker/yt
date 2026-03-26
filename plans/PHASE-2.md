# Phase 2 — FastAPI + CrewAI Backend Scaffold

**Goal**: A running Python backend that accepts trigger requests from Next.js, enqueues Celery tasks,
writes agent status back to Supabase in real-time, and wires the "Run" button end-to-end.
Agents are placeholders — the plumbing is fully real.

**Depends on**: Phase 1 complete (Supabase tables exist, `lib/supabase.ts` exists)

---

## Manual Prerequisites (human does these)

1. Create Upstash Redis at upstash.com → copy REST URL + REST token
2. Add to `.env.local`:
   ```
   BACKEND_URL=http://localhost:8000
   ```
3. Add to `backend/.env` (created by subagent with placeholders):
   ```
   UPSTASH_REDIS_REST_URL=<paste here>
   UPSTASH_REDIS_REST_TOKEN=<paste here>
   ```

---

## New npm Dependency

```bash
npm install zod
```

(if not already installed from Phase 1)

---

## New Python Files to Create

```
backend/
  requirements.txt
  .env.example
  Dockerfile
  docker-compose.yml
  config.py
  main.py
  tasks.py
  crew.py
  agents/
    __init__.py
    strategy.py
    research.py
    content.py
    production.py
    upload.py
    analytics.py
  tools/
    __init__.py
    supabase_tool.py
```

---

## `backend/requirements.txt`

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
crewai==0.80.0
celery==5.4.0
redis==5.0.8
supabase==2.10.0
pydantic-settings==2.5.2
httpx==0.27.2
python-dotenv==1.0.1
google-api-python-client==2.149.0
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.1
anthropic==0.40.0
openai==1.55.3
```

---

## `backend/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase (required)
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # Redis / Celery (required)
    UPSTASH_REDIS_REST_URL: str
    UPSTASH_REDIS_REST_TOKEN: str

    # AI APIs (filled in Phase 3)
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # YouTube (filled in Phase 3)
    YOUTUBE_API_KEY: str = ""
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REFRESH_TOKEN: str = ""

    # Other APIs (filled in Phase 3)
    SUNO_API_KEY: str = ""
    SERPAPI_KEY: str = ""
    REPLICATE_API_TOKEN: str = ""

    # NemoClaw / Telegram (filled in Phase 5)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

settings = Settings()
```

---

## `backend/main.py`

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
from supabase import create_client
from config import settings
from tasks import run_agent_task
import uuid
import datetime

app = FastAPI(title="NemoClaw Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

AgentName = Literal["strategy", "research", "content", "production", "upload", "analytics"]

AGENT_META = {
    "strategy":   {"name": "Strategy Agent",   "role": "Content Strategist & ROI Optimizer"},
    "research":   {"name": "Research Agent",    "role": "YouTube Trend Analyst"},
    "content":    {"name": "Content Agent",     "role": "Title, Thumbnail & Metadata Creator"},
    "production": {"name": "Production Agent",  "role": "Audio Generation & FFmpeg Renderer"},
    "upload":     {"name": "Upload Agent",      "role": "YouTube Data API v3 Publisher"},
    "analytics":  {"name": "Analytics Agent",   "role": "Performance Monitor & Reporter"},
}


class RunAgentRequest(BaseModel):
    agent: AgentName
    input: dict = {}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/run-agent")
def run_agent(body: RunAgentRequest):
    run_id = str(uuid.uuid4())
    db.table("agent_runs").insert({
        "id": run_id,
        "agent_name": body.agent,
        "status": "running",
        "input": body.input,
        "started_at": datetime.datetime.utcnow().isoformat(),
    }).execute()
    run_agent_task.delay(run_id, body.agent, body.input)
    return {"run_id": run_id, "status": "running"}


@app.get("/api/agent-status/{run_id}")
def agent_status(run_id: str):
    result = db.table("agent_runs").select("*").eq("id", run_id).maybe_single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Run not found")
    return result.data


@app.get("/api/agents")
def get_agents():
    result = db.table("agent_runs").select("*").order("started_at", desc=True).limit(300).execute()
    runs = result.data or []

    by_agent: dict[str, list] = {}
    for run in runs:
        name = run["agent_name"]
        by_agent.setdefault(name, []).append(run)

    summaries = []
    for agent_id in AGENT_META:
        agent_runs = by_agent.get(agent_id, [])
        latest = agent_runs[0] if agent_runs else None
        total = len(agent_runs)
        success = sum(1 for r in agent_runs if r["status"] == "success")
        durations = [r["duration_ms"] for r in agent_runs if r.get("duration_ms")]
        avg_ms = int(sum(durations) / len(durations)) if durations else 0

        def fmt_ms(ms: int) -> str:
            if ms < 60000:
                return f"{ms // 1000}s"
            return f"{ms // 60000}m {(ms % 60000) // 1000}s"

        summaries.append({
            "agent_id": agent_id,
            **AGENT_META[agent_id],
            "status": latest["status"] if latest else "idle",
            "last_run": latest["started_at"] if latest else None,
            "run_count": total,
            "success_rate": round(success / total * 100, 1) if total else 0.0,
            "avg_duration": fmt_ms(avg_ms) if avg_ms else "—",
            "output_summary": latest.get("output_summary") if latest else None,
            "full_output": latest.get("full_output") if latest else None,
        })

    return summaries
```

---

## `backend/tasks.py`

```python
from celery import Celery
from celery.schedules import crontab
from supabase import create_client
from config import settings
import datetime
import time

# Upstash Redis URL needs rediss:// scheme for SSL
broker_url = settings.UPSTASH_REDIS_REST_URL.replace("https://", "rediss://:").replace("http://", "redis://:")
if "@" not in broker_url:
    broker_url = broker_url.replace("rediss://:", f"rediss://:{settings.UPSTASH_REDIS_REST_TOKEN}@")
    # Format: rediss://:TOKEN@HOST:PORT

celery_app = Celery("yt_automation", broker=broker_url, backend=broker_url)
celery_app.conf.broker_transport_options = {"visibility_timeout": 3600}
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"

db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def dispatch_agent(agent_name: str, input_data: dict) -> dict:
    """
    Routes to the correct agent module.
    Placeholder implementations until Phase 3 replaces each one.
    """
    # Phase 3 will replace each branch with real agent calls
    log = [
        f"[{datetime.datetime.utcnow().strftime('%H:%M:%S')}] INFO  {agent_name} agent starting (placeholder)...",
        f"[{datetime.datetime.utcnow().strftime('%H:%M:%S')}] INFO  Input: {input_data}",
        f"[{datetime.datetime.utcnow().strftime('%H:%M:%S')}] INFO  Placeholder execution complete.",
        f"[{datetime.datetime.utcnow().strftime('%H:%M:%S')}] INFO  Done — real implementation coming in Phase 3.",
    ]
    return {
        "summary": f"{agent_name} agent ran successfully (placeholder — Phase 3 will add real logic)",
        "log": log,
        "result": {},
        "progress": 100,
    }


@celery_app.task(bind=True, name="run_agent_task")
def run_agent_task(self, run_id: str, agent_name: str, input_data: dict):
    start = time.time()
    try:
        result = dispatch_agent(agent_name, input_data)
        db.table("agent_runs").update({
            "status": "success",
            "output_summary": result["summary"],
            "full_output": result,
            "finished_at": datetime.datetime.utcnow().isoformat(),
            "duration_ms": int((time.time() - start) * 1000),
        }).eq("id", run_id).execute()
    except Exception as exc:
        db.table("agent_runs").update({
            "status": "error",
            "output_summary": str(exc)[:500],
            "finished_at": datetime.datetime.utcnow().isoformat(),
            "duration_ms": int((time.time() - start) * 1000),
        }).eq("id", run_id).execute()
        raise


# Celery Beat schedule
celery_app.conf.beat_schedule = {
    "analytics-daily-4am": {
        "task": "run_agent_task",
        "schedule": crontab(hour=4, minute=0),
        "args": (str(__import__("uuid").uuid4()), "analytics", {}),
    },
}
```

---

## `backend/crew.py`

Minimal CrewAI scaffold — wired properly, agents are stubs until Phase 3.

```python
from crewai import Agent, Crew, Task, Process

def build_crew(agent_name: str, input_data: dict) -> Crew:
    """
    Returns a single-agent Crew for the requested agent.
    Phase 3 will expand each agent with real tools.
    """
    agent = Agent(
        role=f"{agent_name.capitalize()} Agent",
        goal=f"Execute the {agent_name} workflow for the YouTube automation system",
        backstory="AI agent in the NemoClaw YouTube automation pipeline",
        verbose=True,
        allow_delegation=False,
    )
    task = Task(
        description=f"Run {agent_name} workflow with input: {input_data}",
        agent=agent,
        expected_output=f"JSON result from {agent_name} agent",
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
```

---

## `backend/tools/supabase_tool.py`

The one tool all agents use in Phase 2 and beyond — read/write to Supabase.

```python
from supabase import create_client
from config import settings
from typing import Any

class SupabaseTool:
    def __init__(self):
        self.db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    def select(self, table: str, filters: dict = {}, limit: int = 100) -> list[dict]:
        query = self.db.table(table).select("*")
        for key, val in filters.items():
            query = query.eq(key, val)
        return query.limit(limit).execute().data or []

    def insert(self, table: str, data: dict) -> dict:
        result = self.db.table(table).insert(data).execute()
        return result.data[0] if result.data else {}

    def update(self, table: str, data: dict, match: dict) -> None:
        query = self.db.table(table).update(data)
        for key, val in match.items():
            query = query.eq(key, val)
        query.execute()

    def update_run_log(self, run_id: str, log_lines: list[str], progress: int = None) -> None:
        """Append log lines to an agent_run's full_output during execution."""
        current = self.db.table("agent_runs").select("full_output").eq("id", run_id).single().execute()
        existing = current.data.get("full_output") or {}
        existing_log = existing.get("log", [])
        update_data: dict[str, Any] = {"full_output": {**existing, "log": existing_log + log_lines}}
        if progress is not None:
            update_data["full_output"]["progress"] = progress
        self.db.table("agent_runs").update(update_data).eq("id", run_id).execute()
```

---

## `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /sandbox/output

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## `backend/docker-compose.yml` (local dev)

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - .:/app
      - /app/__pycache__

  worker:
    build: .
    env_file: .env
    command: celery -A tasks worker --loglevel=info --concurrency=4
    volumes:
      - .:/app
      - /sandbox/output:/sandbox/output

  beat:
    build: .
    env_file: .env
    command: celery -A tasks beat --loglevel=info
    volumes:
      - .:/app
```

Redis is Upstash (remote) — no local Redis container needed.

---

## New Next.js Files to Create

### `app/api/run-agent/route.ts`

```ts
import { z } from 'zod'
import { NextResponse } from 'next/server'

const schema = z.object({
  agent: z.enum(['strategy', 'research', 'content', 'production', 'upload', 'analytics']),
  input: z.record(z.unknown()).optional().default({}),
})

export async function POST(request: Request) {
  const body = await request.json()
  const parsed = schema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.flatten() }, { status: 400 })
  }
  const res = await fetch(`${process.env.BACKEND_URL}/api/run-agent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(parsed.data),
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
```

### `app/api/agent-status/[id]/route.ts`

```ts
import { NextResponse } from 'next/server'

export async function GET(request: Request, props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params
  const res = await fetch(`${process.env.BACKEND_URL}/api/agent-status/${id}`)
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
```

### `app/api/agents/route.ts`

```ts
import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase'

export async function GET() {
  const { data: runs } = await supabaseAdmin
    .from('agent_runs')
    .select('*')
    .order('started_at', { ascending: false })
    .limit(300)

  return NextResponse.json(runs ?? [])
}
```

---

## New Component: `components/run-agent-button.tsx`

```tsx
'use client'
import { useState } from 'react'
import { Play, Loader2 } from 'lucide-react'

interface RunAgentButtonProps {
  agentId: string
  onTriggered?: (runId: string) => void
}

export function RunAgentButton({ agentId, onTriggered }: RunAgentButtonProps) {
  const [loading, setLoading] = useState(false)

  async function handleRun() {
    setLoading(true)
    try {
      const res = await fetch('/api/run-agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent: agentId, input: {} }),
      })
      const data = await res.json()
      if (data.run_id) onTriggered?.(data.run_id)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleRun}
      disabled={loading}
      className="w-7 h-7 rounded-md flex items-center justify-center transition-colors disabled:opacity-50"
      style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
      title="Trigger run"
    >
      {loading
        ? <Loader2 size={10} className="animate-spin" style={{ color: 'var(--green)' }} />
        : <Play size={10} />}
    </button>
  )
}
```

---

## Files to Update

### `app/agents/page.tsx`

Replace the static `<button>` with `<RunAgentButton agentId={agent.id} />`.
Add `import { RunAgentButton } from '@/components/run-agent-button'`.

---

## End-to-End Flow After Phase 2

1. User clicks "Run" on any agent card → `RunAgentButton` fires
2. `POST /api/run-agent` (Next.js route) validates with Zod, proxies to FastAPI
3. FastAPI writes `{ status: 'running' }` row to `agent_runs`
4. Supabase Realtime fires → activity feed shows "agent started" (from Phase 1 subscription)
5. Celery task executes placeholder → writes `{ status: 'success' }` back to Supabase
6. Activity feed updates live with success row

---

## What Phase 2 Does NOT Include

- No real agent logic (all agents are placeholder responses)
- No YouTube API, Suno, SerpAPI, FFmpeg, Claude — those come in Phase 3
- No Celery Beat actually triggering (can run manually for now)
- No production deployment (Railway/Render setup comes after Phase 3 agents work)
