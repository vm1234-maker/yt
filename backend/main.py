from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Literal
from supabase import create_client
from config import settings
from tasks import run_agent_exec, run_pipeline_task
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

AgentName = Literal[
    "strategy", "research", "content", "production", "upload", "analytics",
    "brainstorm", "setup", "nemoclaw",
]

AGENT_META = {
    "nemoclaw":    {"name": "NemoClaw Orchestrator", "role": "Parent agent — runs an ordered list of agents (input.steps)"},
    "pipeline":    {"name": "Full Pipeline",     "role": "End-to-end orchestrator"},
    "setup":       {"name": "Setup Agent",       "role": "Downloads all CC0 visual & audio loops"},
    "research":    {"name": "Research Agent",    "role": "YouTube Trend Analyst"},
    "brainstorm":  {"name": "Brainstorm Round",  "role": "Multi-agent discussion — Research + Strategy + Content"},
    "content":     {"name": "Content Agent",     "role": "Title, Thumbnail & Metadata Creator"},
    "production":  {"name": "Production Agent",  "role": "Audio Loop + FFmpeg Renderer"},
    "upload":      {"name": "Upload Agent",      "role": "YouTube Data API v3 Publisher"},
    "analytics":   {"name": "Analytics Agent",   "role": "Performance Monitor & Reporter"},
    "strategy":    {"name": "Strategy Agent",    "role": "Content Strategist & ROI Optimizer"},
}


class RunAgentRequest(BaseModel):
    agent: AgentName
    input: dict[str, Any] = Field(default_factory=dict)


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
    run_agent_exec.delay(run_id, body.agent, body.input)
    return {"run_id": run_id, "status": "running"}


@app.get("/api/agent-status/{run_id}")
def agent_status(run_id: str):
    result = db.table("agent_runs").select("*").eq("id", run_id).maybe_single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Run not found")
    return result.data


class RunPipelineRequest(BaseModel):
    input: dict = {}


@app.post("/api/run-pipeline")
def run_pipeline(body: RunPipelineRequest):
    """Kick off the full Research → Brainstorm → Content → [approval] → Production → Upload pipeline."""
    pipeline_run_id = str(uuid.uuid4())
    db.table("agent_runs").insert({
        "id": pipeline_run_id,
        "agent_name": "pipeline",
        "status": "running",
        "input": body.input,
        "started_at": datetime.datetime.utcnow().isoformat(),
        "full_output": {"log": [], "progress": 0},
    }).execute()
    run_pipeline_task.delay(pipeline_run_id, body.input)
    return {"pipeline_run_id": pipeline_run_id, "status": "running"}


@app.get("/api/pipeline-status/{pipeline_run_id}")
def pipeline_status(pipeline_run_id: str):
    result = db.table("agent_runs").select("*").eq("id", pipeline_run_id).maybe_single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
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
