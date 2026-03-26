import datetime
import json
import httpx
import os
from tools.openai_tool import OpenAITool
from tools.supabase_tool import SupabaseTool

PROVEN_THRESHOLD_RETENTION_30 = 0.40   # 40% retention at 30min = niche is proven
DEAD_THRESHOLD_RETENTION_10 = 0.20     # <20% retention at 10min after 5 uploads = kill
MIN_UPLOADS_TO_PROVE = 3
MIN_UPLOADS_TO_KILL = 5


def run_strategy_agent(run_id: str, input_data: dict) -> dict:
    openai_tool = OpenAITool()
    supabase = SupabaseTool()
    log = []

    def ts():
        return datetime.datetime.utcnow().strftime('%H:%M:%S')

    log.append(f"[{ts()}] INFO  Strategy Agent starting ROI analysis...")
    supabase.update_run_log(run_id, log, progress=5)

    # Load data
    analytics = supabase.select("video_analytics", {}, limit=500)
    channel = supabase.select("channel_metrics", {}, limit=1)
    queue = supabase.select("content_queue", {}, limit=200)

    # Load latest research report
    research_runs = supabase.select("agent_runs", {"agent_name": "research", "status": "success"}, limit=1)
    research_data = research_runs[0].get("full_output", {}).get("result", {}) if research_runs else {}

    log.append(f"[{ts()}] INFO  Loaded {len(analytics)} video analytics, {len(queue)} queue items")
    supabase.update_run_log(run_id, log[-1:], progress=15)

    # Group videos by niche
    niche_map: dict[str, list] = {}
    for v in analytics:
        vid = next((q for q in queue if q.get("youtube_video_id") == v.get("youtube_video_id")), {})
        niche = vid.get("niche", "unknown")
        niche_map.setdefault(niche, []).append({**v, "length_hours": vid.get("length_hours", 3)})

    # ROI decisions
    plan: dict = {"exploit": [], "test": [], "kill": [], "niche_decisions": {}}
    for niche, videos in niche_map.items():
        count = len(videos)
        avg_retention_30 = sum(
            v["avg_view_duration_seconds"] / (v["length_hours"] * 3600)
            for v in videos if v.get("avg_view_duration_seconds") and v.get("length_hours")
        ) / max(count, 1)
        avg_retention_10 = sum(
            min(v["avg_view_duration_seconds"] / 600, 1.0) for v in videos if v.get("avg_view_duration_seconds")
        ) / max(count, 1)

        if avg_retention_30 > PROVEN_THRESHOLD_RETENTION_30 and count >= MIN_UPLOADS_TO_PROVE:
            decision = "exploit"
        elif avg_retention_10 < DEAD_THRESHOLD_RETENTION_10 and count >= MIN_UPLOADS_TO_KILL:
            decision = "kill"
        else:
            decision = "test"

        plan[decision].append(niche)
        plan["niche_decisions"][niche] = {
            "decision": decision, "uploads": count,
            "avg_retention_30": round(avg_retention_30, 3),
            "avg_retention_10": round(avg_retention_10, 3),
        }
        log.append(f"[{ts()}] INFO  {niche}: {decision} (uploads={count}, ret30={avg_retention_30:.0%})")

    supabase.update_run_log(run_id, log[-2:], progress=50)

    # Ask Claude to pick the next best niche + angle
    research_niches = research_data.get("niches", [])[:5]
    top_pick_raw = openai_tool.generate_text(f"""
You are the content strategy brain for a YouTube ambient/soundscape channel.

Current performance data:
- Exploit niches (high retention, proven): {plan['exploit']}
- Test niches (collecting data): {plan['test']}
- Kill niches (low retention, drop): {plan['kill']}

Latest research top niches: {json.dumps(research_niches, indent=2)}

Pick the single best niche and angle for the NEXT video to produce.
Prioritize: exploit niches first, then high-score research niches.
Avoid kill niches entirely.

Business rules:
- RPM floor: avoid niches estimated below $8/RPM
- Video length: 3h standard, 8h for sleep content, 1h for focus content
- Content must be unique — no repeating the same niche angle twice in a row

Return ONLY a JSON object:
{{
  "niche": "exact niche name",
  "angle": "specific angle/mood description",
  "length_hours": 3,
  "reasoning": "one sentence explanation"
}}
""")

    try:
        top_pick = json.loads(top_pick_raw.strip())
    except Exception:
        top_pick = {"niche": plan["exploit"][0] if plan["exploit"] else "rain sounds",
                    "angle": "study and focus", "length_hours": 3, "reasoning": "fallback"}

    log.append(f"[{ts()}] INFO  Next video: {top_pick['niche']} — {top_pick['angle']} ({top_pick['length_hours']}h)")
    log.append(f"[{ts()}] INFO  Reasoning: {top_pick.get('reasoning', '')}")
    supabase.update_run_log(run_id, log[-2:], progress=80)

    # Trigger Content Agent for next video
    log.append(f"[{ts()}] INFO  Triggering Content Agent...")
    app_url = os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
    try:
        httpx.post(f"{app_url}/api/run-agent", json={
            "agent": "content",
            "input": {
                "niche": top_pick["niche"],
                "angle": top_pick["angle"],
                "length_hours": top_pick["length_hours"],
            }
        }, timeout=15)
        log.append(f"[{ts()}] INFO  Content Agent triggered successfully")
    except Exception as e:
        log.append(f"[{ts()}] WARN  Failed to trigger Content Agent: {e}")

    supabase.update_run_log(run_id, log[-1:], progress=100)

    return {
        "summary": f"Strategy: exploit={plan['exploit']}, kill={plan['kill']}. Next: {top_pick['niche']} ({top_pick['length_hours']}h)",
        "log": log,
        "result": {"plan": plan, "top_pick": top_pick},
        "progress": 100,
    }
