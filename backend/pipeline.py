"""
Pipeline orchestrator — runs all 6 agents in sequence with a brainstorm discussion.

Flow:
  1. Research Agent      → scans 12 niches, finds content gaps
  2. Brainstorm Round    → Research + Strategy + Content discuss the best angle (4 turns)
  3. Content Agent       → generates title, description, tags, thumbnail
  4. [Human/NemoClaw approval required — pipeline pauses here]
  5. Production Agent    → assembles MP4 from static loops + thumbnail
  6. Upload Agent        → uploads to YouTube on schedule
  7. Analytics Agent     → runs on its own Celery Beat schedule (4am)

Usage:
    from pipeline import run_full_pipeline
    result = run_full_pipeline(run_id)
"""

import datetime
import time
import uuid as _uuid
from config import settings
from tools.supabase_tool import SupabaseTool

APPROVAL_POLL_INTERVAL = 10   # seconds between approval checks
APPROVAL_TIMEOUT = 3600       # 1 hour — cancel if not approved


def _ts():
    return datetime.datetime.utcnow().strftime('%H:%M:%S')


def _log(supabase: SupabaseTool, run_id: str, msg: str, progress: int | None = None):
    print(msg)
    supabase.update_run_log(run_id, [f"[{_ts()}] {msg}"], progress=progress)


def run_full_pipeline(pipeline_run_id: str, input_data: dict | None = None) -> dict:
    """
    Execute the full agent pipeline sequentially.
    Each step passes its output to the next.
    Returns a summary dict when complete (or when paused at approval).
    """
    input_data = input_data or {}
    supabase = SupabaseTool()
    results: dict = {}

    _log(supabase, pipeline_run_id, "INFO  🚀 Pipeline starting — Research → Brainstorm → Content → [approval] → Production → Upload", progress=2)

    # ─────────────────────────────────────────────────────
    # STEP 1: Research Agent
    # ─────────────────────────────────────────────────────
    _log(supabase, pipeline_run_id, "INFO  ── Step 1/6: Research Agent", progress=5)
    research_run_id = str(_uuid.uuid4())
    supabase.log_agent_run(research_run_id, "research", input_data, pipeline_run_id=pipeline_run_id)

    try:
        from agents.research import run_research_agent
        research_result = run_research_agent(research_run_id, input_data)
        supabase.complete_agent_run(research_run_id, research_result)
        results["research"] = research_result
        niches = research_result.get("result", {}).get("niches", [])
        _log(supabase, pipeline_run_id, f"INFO  ✅ Research done — top niche: {niches[0]['name'] if niches else 'unknown'}", progress=18)
    except Exception as e:
        _log(supabase, pipeline_run_id, f"ERROR ❌ Research failed: {e}", progress=18)
        supabase.fail_agent_run(research_run_id, str(e))
        return {"summary": f"Pipeline failed at Research: {e}", "step": "research", "progress": 18}

    # ─────────────────────────────────────────────────────
    # STEP 2: Brainstorm Discussion Round
    # ─────────────────────────────────────────────────────
    _log(supabase, pipeline_run_id, "INFO  ── Step 2/6: Brainstorm (Research + Strategy + Content discuss)", progress=20)
    brainstorm_run_id = str(_uuid.uuid4())
    supabase.log_agent_run(brainstorm_run_id, "brainstorm", {}, pipeline_run_id=pipeline_run_id)

    try:
        from agents.brainstorm import run_brainstorm

        # Load performance history for Strategy Agent's voice
        analytics = supabase.select("video_analytics", {}, limit=500)
        queue = supabase.select("content_queue", {}, limit=200)
        channel_rows = supabase.select("channel_metrics", {}, limit=1)
        channel_metrics = channel_rows[0] if channel_rows else {}

        # Build niche decisions from history
        niche_map: dict = {}
        for v in analytics:
            vid = next((q for q in queue if q.get("youtube_video_id") == v.get("youtube_video_id")), {})
            niche = vid.get("niche", "unknown")
            niche_map.setdefault(niche, []).append(v)

        niche_decisions: dict = {}
        for niche, videos in niche_map.items():
            count = len(videos)
            avg_r30 = sum(
                v.get("avg_view_duration_seconds", 0) / (vid.get("length_hours", 3) * 3600)
                for v, vid in zip(videos, [next((q for q in queue if q.get("youtube_video_id") == v.get("youtube_video_id")), {}) for v in videos])
                if v.get("avg_view_duration_seconds")
            ) / max(count, 1)
            avg_r10 = sum(
                min(v.get("avg_view_duration_seconds", 0) / 600, 1.0) for v in videos
            ) / max(count, 1)
            if avg_r30 > 0.40 and count >= 3:
                decision = "exploit"
            elif avg_r10 < 0.20 and count >= 5:
                decision = "kill"
            else:
                decision = "test"
            niche_decisions[niche] = {
                "decision": decision, "uploads": count,
                "avg_retention_30": round(avg_r30, 3), "avg_retention_10": round(avg_r10, 3),
            }

        brainstorm_result = run_brainstorm(
            run_id=brainstorm_run_id,
            research_niches=niches,
            niche_decisions=niche_decisions,
            channel_metrics=channel_metrics,
        )
        supabase.complete_agent_run(brainstorm_run_id, {
            "summary": f"Brainstorm complete. Winner: {brainstorm_result['final_pick']['niche']} — {brainstorm_result['final_pick']['angle']}",
            "result": brainstorm_result,
            "log": [t["message"] for t in brainstorm_result["discussion"]],
            "progress": 100,
        })
        results["brainstorm"] = brainstorm_result
        final_pick = brainstorm_result["final_pick"]
        _log(supabase, pipeline_run_id, f"INFO  ✅ Brainstorm done — winner: {final_pick['niche']} / {final_pick['angle']}", progress=38)
    except Exception as e:
        _log(supabase, pipeline_run_id, f"ERROR ❌ Brainstorm failed: {e}", progress=38)
        supabase.fail_agent_run(brainstorm_run_id, str(e))
        # Fall back to top niche from research
        final_pick = {
            "niche": niches[0]["name"] if niches else "rain sounds",
            "angle": "study and focus",
            "length_hours": 3,
            "title_concept": "",
            "reasoning": f"Brainstorm failed ({e}), using top research pick",
        }
        results["brainstorm"] = {"final_pick": final_pick, "discussion": []}

    # ─────────────────────────────────────────────────────
    # STEP 3: Content Agent
    # ─────────────────────────────────────────────────────
    _log(supabase, pipeline_run_id, f"INFO  ── Step 3/6: Content Agent ({final_pick['niche']} / {final_pick['angle']})", progress=40)
    content_run_id = str(_uuid.uuid4())
    content_input = {
        "niche": final_pick["niche"],
        "angle": final_pick["angle"],
        "length_hours": final_pick["length_hours"],
        "title_concept": final_pick.get("title_concept", ""),
        "brainstorm_reasoning": final_pick.get("reasoning", ""),
        "priority": "high",
        "pipeline_run_id": pipeline_run_id,
        "brainstorm_run_id": brainstorm_run_id,
    }
    supabase.log_agent_run(content_run_id, "content", content_input, pipeline_run_id=pipeline_run_id)

    try:
        from agents.content import run_content_agent
        content_result = run_content_agent(content_run_id, content_input)
        supabase.complete_agent_run(content_run_id, content_result)
        results["content"] = content_result
        content_id = content_result.get("result", {}).get("content_id", "")
        title = content_result.get("result", {}).get("title", "")
        _log(supabase, pipeline_run_id, f"INFO  ✅ Content brief created: '{title}' (ID: {content_id})", progress=58)
    except Exception as e:
        _log(supabase, pipeline_run_id, f"ERROR ❌ Content Agent failed: {e}", progress=58)
        supabase.fail_agent_run(content_run_id, str(e))
        return {"summary": f"Pipeline failed at Content: {e}", "step": "content", "progress": 58}

    # ─────────────────────────────────────────────────────
    # STEP 4: Approval gate — wait for human/NemoClaw, or auto-approve (AUTO_APPROVE_AFTER_CONTENT)
    # ─────────────────────────────────────────────────────
    _log(supabase, pipeline_run_id, f"INFO  ── Step 4/6: ⏳ Approval for content ID: {content_id}", progress=60)

    approved_content = None
    if settings.AUTO_APPROVE_AFTER_CONTENT:
        now_iso = datetime.datetime.utcnow().isoformat()
        supabase.update("content_queue", {"status": "approved", "approved_at": now_iso}, {"id": content_id})
        rows = supabase.select("content_queue", {"id": content_id}, limit=1)
        if rows:
            approved_content = rows[0]
            _log(supabase, pipeline_run_id, "INFO  🤖 AUTO_APPROVE_AFTER_CONTENT — proceeding to Production", progress=62)
        else:
            _log(supabase, pipeline_run_id, "ERROR  Auto-approve could not reload content row", progress=62)
            return {
                "summary": "Pipeline failed: content row missing after auto-approve",
                "step": "approval",
                "content_id": content_id,
                "progress": 62,
            }
    else:
        elapsed = 0
        while elapsed < APPROVAL_TIMEOUT:
            rows = supabase.select("content_queue", {"id": content_id}, limit=1)
            if rows:
                row = rows[0]
                status = row.get("status", "")
                if status == "approved":
                    approved_content = row
                    _log(supabase, pipeline_run_id, "INFO  ✅ Content approved — proceeding to Production", progress=62)
                    break
                elif status == "rejected":
                    _log(supabase, pipeline_run_id, "INFO  ⛔ Content rejected — pipeline stopped", progress=62)
                    return {
                        "summary": f"Pipeline stopped: content '{title}' was rejected",
                        "step": "approval",
                        "content_id": content_id,
                        "progress": 62,
                    }
            time.sleep(APPROVAL_POLL_INTERVAL)
            elapsed += APPROVAL_POLL_INTERVAL
            if elapsed % 60 == 0:
                _log(supabase, pipeline_run_id, f"INFO  ⏳ Still waiting for approval ({elapsed // 60}m elapsed)...")

    if not approved_content:
        _log(supabase, pipeline_run_id, "WARN  ⏱ Approval timeout — pipeline paused", progress=62)
        return {
            "summary": f"Pipeline paused: approval timeout for '{title}'",
            "step": "approval_timeout",
            "content_id": content_id,
            "progress": 62,
        }

    # ─────────────────────────────────────────────────────
    # STEP 5: Production Agent
    # ─────────────────────────────────────────────────────
    _log(supabase, pipeline_run_id, "INFO  ── Step 5/6: Production Agent (assembling video)", progress=65)
    production_run_id = str(_uuid.uuid4())
    production_input = {
        "content_id": content_id,
        "niche": final_pick["niche"],
        "title": title,
        "length_hours": final_pick["length_hours"],
        "thumbnail_url": approved_content.get("thumbnail_url", ""),
    }
    supabase.log_agent_run(production_run_id, "production", production_input, pipeline_run_id=pipeline_run_id)

    try:
        from agents.production import run_production_agent
        production_result = run_production_agent(production_run_id, production_input)
        supabase.complete_agent_run(production_run_id, production_result)
        results["production"] = production_result
        video_url = production_result.get("result", {}).get("video_url", "")
        _log(supabase, pipeline_run_id, f"INFO  ✅ Video assembled: {video_url[:60] if video_url else 'no URL'}...", progress=80)
    except Exception as e:
        _log(supabase, pipeline_run_id, f"ERROR ❌ Production failed: {e}", progress=80)
        supabase.fail_agent_run(production_run_id, str(e))
        return {"summary": f"Pipeline failed at Production: {e}", "step": "production", "progress": 80}

    # ─────────────────────────────────────────────────────
    # STEP 6: Upload Agent
    # ─────────────────────────────────────────────────────
    _log(supabase, pipeline_run_id, "INFO  ── Step 6/6: Upload Agent (pushing to YouTube)", progress=82)
    upload_run_id = str(_uuid.uuid4())
    upload_input = {
        "content_id": content_id,
        "video_url": video_url,
        "title": title,
        "description": approved_content.get("description", ""),
        "tags": approved_content.get("tags", []),
        "thumbnail_url": approved_content.get("thumbnail_url", ""),
        "niche": final_pick["niche"],
        "length_hours": final_pick["length_hours"],
        "schedule": input_data.get("schedule", "immediate"),
    }
    supabase.log_agent_run(upload_run_id, "upload", upload_input, pipeline_run_id=pipeline_run_id)

    try:
        from agents.upload import run_upload_agent
        upload_result = run_upload_agent(upload_run_id, upload_input)
        supabase.complete_agent_run(upload_run_id, upload_result)
        results["upload"] = upload_result
        yt_id = upload_result.get("result", {}).get("youtube_video_id", "")
        _log(supabase, pipeline_run_id, f"INFO  ✅ Uploaded to YouTube: https://youtu.be/{yt_id}", progress=100)
    except Exception as e:
        _log(supabase, pipeline_run_id, f"ERROR ❌ Upload failed: {e}", progress=100)
        supabase.fail_agent_run(upload_run_id, str(e))
        return {"summary": f"Pipeline failed at Upload: {e}", "step": "upload", "progress": 100}

    return {
        "summary": f"✅ Full pipeline complete — '{title}' uploaded to YouTube (ID: {yt_id})",
        "step": "complete",
        "content_id": content_id,
        "youtube_video_id": yt_id,
        "discussion_turns": len(results.get("brainstorm", {}).get("discussion", [])),
        "progress": 100,
    }
