from celery import Celery
from celery.schedules import crontab
from supabase import create_client
from config import settings
import datetime
import time

# Build rediss:// URL for Upstash SSL — strip https://, inject :TOKEN@ before host
# ssl_cert_reqs=CERT_NONE required by Celery 5.4+ for rediss:// connections
_host = settings.UPSTASH_REDIS_REST_URL.replace("https://", "").replace("http://", "")
broker_url = f"rediss://:{settings.UPSTASH_REDIS_REST_TOKEN}@{_host}:6379?ssl_cert_reqs=CERT_NONE"

celery_app = Celery("yt_automation", broker=broker_url, backend=broker_url)
celery_app.conf.broker_transport_options = {"visibility_timeout": 3600}
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"

db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def dispatch_agent(run_id: str, agent_name: str, input_data: dict) -> dict:
    """Routes to the correct agent module."""
    if agent_name == "research":
        from agents.research import run_research_agent
        return run_research_agent(run_id, input_data)
    elif agent_name == "content":
        from agents.content import run_content_agent
        return run_content_agent(run_id, input_data)
    elif agent_name == "production":
        from agents.production import run_production_agent
        return run_production_agent(run_id, input_data)
    elif agent_name == "upload":
        from agents.upload import run_upload_agent
        return run_upload_agent(run_id, input_data)
    elif agent_name == "analytics":
        from agents.analytics import run_analytics_agent
        return run_analytics_agent(run_id, input_data)
    elif agent_name == "strategy":
        from agents.strategy import run_strategy_agent
        return run_strategy_agent(run_id, input_data)
    elif agent_name == "setup":
        from agents.setup import run_setup_agent
        return run_setup_agent(run_id, input_data)
    else:
        raise ValueError(f"Unknown agent: {agent_name}")


@celery_app.task(bind=True, name="run_scheduled_pipeline")
def run_scheduled_pipeline(self):
    """Insert pipeline agent_runs row and enqueue full pipeline (optional weekly schedule)."""
    import uuid as _uuid

    pipeline_run_id = str(_uuid.uuid4())
    db.table("agent_runs").insert({
        "id": pipeline_run_id,
        "agent_name": "pipeline",
        "status": "running",
        "input": {},
        "started_at": datetime.datetime.utcnow().isoformat(),
    }).execute()
    run_pipeline_task.delay(pipeline_run_id, {})


@celery_app.task(bind=True, name="run_pipeline_task")
def run_pipeline_task(self, pipeline_run_id: str, input_data: dict):
    """Run the full 6-agent pipeline with brainstorm discussion."""
    start = time.time()
    try:
        from pipeline import run_full_pipeline
        result = run_full_pipeline(pipeline_run_id, input_data)
        db.table("agent_runs").update({
            "status": "success" if result.get("step") == "complete" else "running",
            "output_summary": result.get("summary", "")[:500],
            "full_output": result,
            "finished_at": datetime.datetime.utcnow().isoformat(),
            "duration_ms": int((time.time() - start) * 1000),
        }).eq("id", pipeline_run_id).execute()
    except Exception as exc:
        db.table("agent_runs").update({
            "status": "error",
            "output_summary": str(exc)[:500],
            "finished_at": datetime.datetime.utcnow().isoformat(),
            "duration_ms": int((time.time() - start) * 1000),
        }).eq("id", pipeline_run_id).execute()
        raise


@celery_app.task(bind=True, name="run_scheduled_agent")
def run_scheduled_agent(self, agent_name: str, input_data: dict | None = None):
    """Create agent_runs row then enqueue run_agent_task (Beat must use this — not run_agent_task alone)."""
    import uuid as _uuid

    input_data = input_data or {}
    run_id = str(_uuid.uuid4())
    db.table("agent_runs").insert({
        "id": run_id,
        "agent_name": agent_name,
        "status": "running",
        "input": input_data,
        "started_at": datetime.datetime.utcnow().isoformat(),
    }).execute()
    run_agent_task.delay(run_id, agent_name, input_data)


@celery_app.task(bind=True, name="run_agent_task")
def run_agent_task(self, run_id: str, agent_name: str, input_data: dict):
    start = time.time()
    try:
        result = dispatch_agent(run_id, agent_name, input_data)
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


# Celery Beat schedule — use run_scheduled_agent so each run gets a fresh agent_runs row
celery_app.conf.beat_schedule = {
    "analytics-daily-4am": {
        "task": "run_scheduled_agent",
        "schedule": crontab(hour=4, minute=0),
        "kwargs": {"agent_name": "analytics", "input_data": {}},
    },
}

if settings.AUTO_STRATEGY_WEEKLY:
    celery_app.conf.beat_schedule["strategy-weekly-mon-6am"] = {
        "task": "run_scheduled_agent",
        "schedule": crontab(hour=6, minute=0, day_of_week=1),
        "kwargs": {"agent_name": "strategy", "input_data": {}},
    }

if settings.AUTO_PIPELINE_WEEKLY:
    celery_app.conf.beat_schedule["pipeline-weekly-sun-10am-utc"] = {
        "task": "run_scheduled_pipeline",
        "schedule": crontab(hour=10, minute=0, day_of_week=0),
        "args": (),
    }


def _subscriber_line(channel: dict) -> str:
    total = channel.get("total_subscribers")
    gained = channel.get("subscribers_gained")
    legacy = channel.get("subscribers")
    if total is not None:
        return f"Total subs: {int(total):,}"
    if gained is not None:
        return f"Subscribers (period): {int(gained):,}"
    if legacy is not None:
        return f"Subscribers: {int(legacy):,}"
    return "Subscribers: —"


def _send_daily_digest_imessage(msg: str) -> None:
    """iMessage only (AppleScript). Requires Celery Beat to run on macOS — not inside Linux Docker."""
    import os as _os
    import sys

    sys.path.insert(
        0,
        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'nemoclaw', 'tools'),
    )
    if not settings.IMESSAGE_RECIPIENT:
        print("[nemoclaw_daily_summary] IMESSAGE_RECIPIENT not set — skipping send")
        return
    try:
        from send_imessage import send_imessage
        send_imessage(msg)
    except Exception as exc:
        print(f"[nemoclaw_daily_summary] iMessage failed: {exc}")


@celery_app.task(name="nemoclaw_daily_summary")
def nemoclaw_daily_summary():
    """Build morning report; send via iMessage (macOS host with Messages + Beat)."""
    import sys
    import os as _os
    sys.path.insert(
        0,
        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'nemoclaw', 'tools'),
    )
    from read_analytics import read_analytics
    import datetime

    channel = read_analytics("channel")
    videos = read_analytics("videos", limit=5)["videos"]
    runs = read_analytics("agent_runs", filters={}, limit=20)["runs"]

    top = videos[0] if videos else {}
    today = datetime.date.today().strftime("%a %b %d %Y")
    sub_line = _subscriber_line(channel)

    msg = f"""🎵 NemoClaw Daily Report — {today}

📈 Top Video
{top.get('title', 'N/A')} — {top.get('views', 0):,} views, est. ${top.get('estimated_revenue', 0):.2f}

📊 Channel This Week
Views: {channel.get('total_views', 0):,} | Watch Hours: {channel.get('total_watch_hours', 0):.0f}h
Revenue: ${channel.get('estimated_revenue', 0):.2f} | {sub_line}

🤖 Recent Agent Runs
""" + "\n".join(
        f"{'✅' if r['status'] == 'success' else '❌'} {r['agent_name'].title()} — {r.get('output_summary', '')[:60]}"
        for r in runs[:5]
    )

    _send_daily_digest_imessage(msg)


celery_app.conf.beat_schedule["nemoclaw-daily-8am"] = {
    "task": "nemoclaw_daily_summary",
    "schedule": crontab(hour=8, minute=0),
    "args": (),
}
