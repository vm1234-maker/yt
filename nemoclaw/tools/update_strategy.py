from supabase import create_client
import os
import datetime


def _db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def update_strategy(notes: str) -> dict:
    """Write strategic notes that the Strategy Agent will read on its next run."""
    db = _db()
    db.table("agent_runs").insert({
        "agent_name": "nemoclaw_notes",
        "status": "success",
        "output_summary": notes[:500],
        "full_output": {"notes": notes, "type": "strategy_directive"},
        "started_at": datetime.datetime.utcnow().isoformat(),
        "finished_at": datetime.datetime.utcnow().isoformat(),
    }).execute()
    return {"noted": True}
