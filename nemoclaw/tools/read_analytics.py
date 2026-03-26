from supabase import create_client
import os
from typing import Literal, Optional
import datetime


def _db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def read_analytics(
    type: Literal["videos", "channel", "content_queue", "agent_runs", "research"] = "channel",
    filters: Optional[dict] = None,
    limit: int = 20,
) -> dict:
    """
    Read analytics data from Supabase.
    type:
      - "videos" → video_analytics, most recent rows
      - "channel" → channel_metrics, latest rollup
      - "content_queue" → content_queue items (filter by status)
      - "agent_runs" → agent_runs (filter by agent_name or status)
      - "research" → latest research agent output
    """
    db = _db()

    if type == "channel":
        result = db.table("channel_metrics").select("*").order("recorded_at", desc=True).limit(1).execute()
        return result.data[0] if result.data else {}

    elif type == "videos":
        q = db.table("video_analytics").select("*").order("recorded_at", desc=True)
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        return {"videos": q.limit(limit).execute().data or []}

    elif type == "content_queue":
        q = db.table("content_queue").select("*").order("created_at", desc=True)
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        return {"queue": q.limit(limit).execute().data or []}

    elif type == "agent_runs":
        q = db.table("agent_runs").select("*").order("started_at", desc=True)
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        return {"runs": q.limit(limit).execute().data or []}

    elif type == "research":
        result = (
            db.table("agent_runs")
            .select("full_output")
            .eq("agent_name", "research")
            .eq("status", "success")
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0].get("full_output", {}).get("result", {})
        return {}

    return {}
