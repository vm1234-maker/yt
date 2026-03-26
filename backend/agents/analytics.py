import datetime
from tools.youtube_analytics import YouTubeAnalyticsTool
from tools.supabase_tool import SupabaseTool


def run_analytics_agent(run_id: str, input_data: dict) -> dict:
    analytics = YouTubeAnalyticsTool()
    supabase = SupabaseTool()
    log = []

    def ts():
        return datetime.datetime.utcnow().strftime('%H:%M:%S')

    # Fetch all uploaded/scheduled videos
    videos = supabase.select("content_queue", {}, limit=200)
    active = [v for v in videos if v.get("status") in ("scheduled", "uploaded") and v.get("youtube_video_id")]
    log.append(f"[{ts()}] INFO  Analytics Agent starting — {len(active)} videos to process")
    supabase.update_run_log(run_id, log, progress=5)

    processed = 0
    total_revenue = 0.0

    for i, video in enumerate(active):
        vid_id = video["youtube_video_id"]
        log.append(f"[{ts()}] INFO  Fetching metrics for: {video.get('title', vid_id)[:40]}")
        supabase.update_run_log(run_id, log[-1:], progress=int(5 + (i / max(len(active), 1)) * 70))

        try:
            metrics = analytics.get_video_metrics(vid_id)
            if metrics:
                rpm = round(metrics["estimated_revenue"] / (metrics["watch_time_minutes"] / 60) * 1000, 2) if metrics.get("watch_time_minutes", 0) > 0 else 0
                supabase.insert("video_analytics", {
                    "youtube_video_id": vid_id,
                    "title": video.get("title"),
                    "niche": video.get("niche"),
                    "views": metrics["views"],
                    "impressions": metrics.get("impressions", 0),
                    "watch_time_minutes": metrics["watch_time_minutes"],
                    "rpm": rpm,
                    "ctr": metrics["ctr"],
                    "avg_view_duration_seconds": metrics["avg_view_duration_seconds"],
                    "estimated_revenue": metrics["estimated_revenue"],
                })
                total_revenue += metrics["estimated_revenue"]
                processed += 1
                log.append(f"[{ts()}] INFO  {video.get('title','')[:30]}: {metrics['views']} views, RPM ${rpm:.2f}")
        except Exception as e:
            log.append(f"[{ts()}] WARN  Failed for {vid_id}: {e}")

    # Channel rollup
    log.append(f"[{ts()}] INFO  Fetching channel rollup...")
    supabase.update_run_log(run_id, log[-1:], progress=80)
    try:
        rollup = analytics.get_channel_rollup()
        supabase.insert("channel_metrics", {
            "total_views": rollup["total_views"],
            "total_watch_hours": rollup["total_watch_hours"],
            "estimated_revenue": rollup["estimated_revenue"],
            "subscribers_gained": rollup.get("subscribers_gained", 0),
            "avg_rpm": round(total_revenue / max(processed, 1), 2),
            "avg_ctr": rollup["avg_ctr"],
            "period_start": rollup["period_start"],
            "period_end": rollup["period_end"],
        })
        log.append(f"[{ts()}] INFO  Channel rollup: {rollup['total_views']} views, ${rollup['estimated_revenue']:.2f} revenue")
    except Exception as e:
        log.append(f"[{ts()}] WARN  Channel rollup failed: {e}")

    supabase.update_run_log(run_id, [f"[{ts()}] INFO  Done. {processed}/{len(active)} videos processed."], progress=100)

    return {
        "summary": f"Analytics complete — {processed} videos processed, est. revenue ${total_revenue:.2f}",
        "log": log,
        "result": {"processed": processed, "total_revenue": total_revenue},
        "progress": 100,
    }
