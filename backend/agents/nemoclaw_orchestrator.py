"""
Parent / orchestrator agent — runs a ordered list of factory agents in one Celery task.

Input (JSON on agent_runs.input and POST /api/run-agent):
  { "steps": [ { "agent": "research", "input": {} }, ... ] }

Allowed child agents: strategy, research, content, production, upload, analytics, setup
(not pipeline, nemoclaw, brainstorm — use Full Pipeline for those.)

Each child gets its own agent_runs row; pipeline_run_id points at the parent run for tracing.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

ALLOWED_CHILD = frozenset(
    {"strategy", "research", "content", "production", "upload", "analytics", "setup"}
)


def run_nemoclaw_orchestrator(parent_run_id: str, input_data: dict) -> dict:
    from tasks import db, execute_single_agent_run

    steps = input_data.get("steps")
    if not isinstance(steps, list):
        raise ValueError('nemoclaw requires input.steps to be a list, e.g. [{"agent":"research","input":{}}]')
    if not steps:
        raise ValueError(
            "nemoclaw requires at least one step, e.g. "
            '{"steps":[{"agent":"research","input":{}}]}'
        )

    children: list[dict[str, Any]] = []
    log: list[str] = []

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"Step {i} must be an object with agent and optional input")
        agent = step.get("agent")
        inp = step.get("input") if isinstance(step.get("input"), dict) else {}
        if agent not in ALLOWED_CHILD:
            raise ValueError(
                f"Step {i}: invalid agent {agent!r}. Allowed: {sorted(ALLOWED_CHILD)}"
            )

        child_id = str(uuid.uuid4())
        db.table("agent_runs").insert(
            {
                "id": child_id,
                "agent_name": agent,
                "status": "running",
                "input": inp,
                "started_at": datetime.datetime.utcnow().isoformat(),
                "pipeline_run_id": parent_run_id,
            }
        ).execute()

        out = execute_single_agent_run(child_id, agent, inp)
        children.append(
            {
                "agent": agent,
                "run_id": child_id,
                "status": "success",
                "summary": (out.get("summary") or "")[:300],
            }
        )
        log.append(f"[{agent}] ok — {child_id[:8]}…")

    names = " → ".join(c["agent"] for c in children)
    summary = f"NemoClaw orchestrator: {len(children)} steps — {names}"
    return {
        "summary": summary[:500],
        "result": {"children": children, "step_count": len(children)},
        "log": log,
    }
