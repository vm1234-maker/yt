import datetime
from tools.youtube_upload import YouTubeUploadTool
from tools.supabase_tool import SupabaseTool


def run_upload_agent(run_id: str, input_data: dict) -> dict:
    content_id = input_data.get("content_id")
    scheduled_for = input_data.get("scheduled_for")  # ISO 8601 UTC string or None

    uploader = YouTubeUploadTool()
    supabase = SupabaseTool()
    log = []

    def ts():
        return datetime.datetime.utcnow().strftime('%H:%M:%S')

    rows = supabase.select("content_queue", {"id": content_id}, limit=1)
    if not rows:
        raise ValueError(f"content_id {content_id} not found")
    content = rows[0]

    if not content.get("video_url"):
        raise ValueError("content has no video_url — run Production Agent first")

    log.append(f"[{ts()}] INFO  Upload Agent starting: {content['title']}")
    log.append(f"[{ts()}] INFO  Loading video from: {content['video_url'][:60]}...")
    supabase.update_run_log(run_id, log, progress=10)

    video_id = uploader.upload(
        video_path=content["video_url"],
        title=content["title"],
        description=content.get("description", ""),
        tags=content.get("tags") or [],
        scheduled_for=scheduled_for,
    )
    log.append(f"[{ts()}] INFO  Upload complete — YouTube ID: {video_id}")
    supabase.update_run_log(run_id, log[-1:], progress=70)

    if content.get("thumbnail_url"):
        log.append(f"[{ts()}] INFO  Setting thumbnail...")
        uploader.set_thumbnail(video_id, content["thumbnail_url"])
        log.append(f"[{ts()}] INFO  Thumbnail set")
        supabase.update_run_log(run_id, log[-1:], progress=85)

    supabase.update("content_queue", {
        "youtube_video_id": video_id,
        "status": "scheduled" if scheduled_for else "uploaded",
        "scheduled_for": scheduled_for,
    }, {"id": content_id})

    log.append(f"[{ts()}] INFO  content_queue updated — status: {'scheduled' if scheduled_for else 'uploaded'}")
    supabase.update_run_log(run_id, log[-1:], progress=100)

    return {
        "summary": f"Uploaded '{content['title']}' — YouTube ID: {video_id}",
        "log": log,
        "result": {"youtube_video_id": video_id, "content_id": content_id},
        "progress": 100,
    }
