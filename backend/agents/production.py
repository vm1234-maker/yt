import datetime
import uuid
import os
import random
from pathlib import Path
from tools.openai_tool import OpenAITool
from tools.ffmpeg_tool import FFmpegTool
from tools.supabase_tool import SupabaseTool
from tools.supabase_storage import SupabaseStorageTool

SANDBOX = Path("/sandbox/output")

VISUALS_DIR = Path(__file__).parent.parent / "visuals"
AUDIO_DIR = Path(__file__).parent.parent / "audio"

# Base niche slug → filesystem prefix (files are named {prefix}_1.mp4, _2.mp4, …)
NICHE_VISUAL_MAP = {
    "rain sounds":          "rain_sounds",
    "lo-fi study music":    "lofi_study_music",
    "dark forest ambiance": "dark_forest_ambiance",
    "coffee shop ambiance": "coffee_shop_ambiance",
    "fireplace crackle":    "fireplace_crackle",
    "thunderstorm sounds":  "thunderstorm_sounds",
    "binaural beats":       "binaural_beats",
    "sleep sounds anxiety": "sleep_sounds_anxiety",
    "nature ASMR":          "nature_asmr",
    "white noise":          "white_noise",
    "ocean waves sleep":    "ocean_waves_sleep",
    "forest birds morning": "forest_birds_morning",
}

THUMBNAIL_PROMPTS = {
    "rain sounds": "cinematic rain falling on dark forest floor, moody atmospheric lighting, deep blue tones, photorealistic",
    "lo-fi study music": "cozy anime bedroom at night, warm desk lamp, rain on window, stacks of books, soft warm light",
    "dark forest ambiance": "ancient dark forest at midnight, fog drifting between tall trees, moonlight through branches",
    "coffee shop ambiance": "warm cozy coffee shop interior, soft golden light, steam from cups, rain visible through window",
    "fireplace crackle": "close-up crackling fireplace flames, orange amber embers, warm hearth glow, cozy stone mantle",
    "thunderstorm sounds": "dramatic storm over dark forest, lightning illuminating clouds, heavy rain, cinematic wide shot",
    "binaural beats": "abstract flowing aurora borealis, deep purple and teal, infinite depth, meditative",
    "sleep sounds anxiety": "calm ocean at night, full moon reflection on still water, soft waves, deep blue silver",
    "nature ASMR": "sunlit forest clearing, golden hour light through leaves, soft bokeh, moss and ferns, peaceful",
    "white noise": "soft abstract gradient fog, slowly shifting shades of white and pale blue, minimal, meditative",
    "ocean waves sleep": "moonlit ocean beach at night, gentle waves, stars visible, deep blue",
    "forest birds morning": "forest at golden sunrise, warm light through trees, misty morning, birds silhouette on branches",
}

NICHE_AUDIO_MAP = {
    "rain sounds":          "rain_sounds",
    "lo-fi study music":    "lofi_study_music",
    "dark forest ambiance": "dark_forest_ambiance",
    "coffee shop ambiance": "coffee_shop_ambiance",
    "fireplace crackle":    "fireplace_crackle",
    "thunderstorm sounds":  "thunderstorm_sounds",
    "binaural beats":       "binaural_beats",
    "sleep sounds anxiety": "sleep_sounds_anxiety",
    "nature ASMR":          "nature_asmr",
    "white noise":          "white_noise",
    "ocean waves sleep":    "ocean_waves_sleep",
    "forest birds morning": "forest_birds_morning",
}

DEFAULT_THUMB_PROMPT = "cinematic ambient atmospheric landscape, moody lighting, beautiful, photorealistic"


def _pick_variant(directory: Path, prefix: str, ext: str) -> Path | None:
    """
    Find all files matching {prefix}_N.{ext} and return a random one.
    Falls back to {prefix}.{ext} (legacy single file) if no numbered variants exist.
    Returns None if nothing found.
    """
    variants = sorted(directory.glob(f"{prefix}_*.{ext}"))
    if variants:
        return random.choice(variants)
    legacy = directory / f"{prefix}.{ext}"
    if legacy.exists() and legacy.stat().st_size > 10_000:
        return legacy
    return None


def get_audio_path(niche: str, log_fn=None) -> str:
    """Return a randomly selected audio loop variant, auto-downloading if nothing found."""
    from tools.asset_downloader import download_audio
    prefix = NICHE_AUDIO_MAP.get(niche, "default")
    chosen = _pick_variant(AUDIO_DIR, prefix, "mp3")
    if chosen:
        if log_fn:
            log_fn(f"[production] Audio variant selected: {chosen.name}")
        return str(chosen)
    # Fall back to default prefix
    chosen = _pick_variant(AUDIO_DIR, "default", "mp3")
    if chosen:
        if log_fn:
            log_fn(f"[production] Audio for '{niche}' missing — using default")
        return str(chosen)
    # Auto-download
    if log_fn:
        log_fn(f"[production] Auto-downloading audio for '{niche}'...")
    filename = f"{prefix}_1.mp3"
    return download_audio(niche, filename)


def get_visual_path(niche: str, log_fn=None) -> str:
    """Return a randomly selected visual loop variant, auto-downloading if nothing found."""
    from tools.asset_downloader import download_visual
    prefix = NICHE_VISUAL_MAP.get(niche, "default")
    chosen = _pick_variant(VISUALS_DIR, prefix, "mp4")
    if chosen:
        if log_fn:
            log_fn(f"[production] Visual variant selected: {chosen.name}")
        return str(chosen)
    # Fall back to default
    chosen = _pick_variant(VISUALS_DIR, "default", "mp4")
    if chosen:
        if log_fn:
            log_fn(f"[production] Visual for '{niche}' missing — using default")
        return str(chosen)
    # Auto-download
    if log_fn:
        log_fn(f"[production] Auto-downloading visual for '{niche}'...")
    filename = f"{prefix}_1.mp4"
    return download_visual(niche, filename)


def run_production_agent(run_id: str, input_data: dict) -> dict:
    content_id = input_data.get("content_id")
    if not content_id:
        raise ValueError("production agent requires content_id in input")

    openai_tool = OpenAITool()
    ffmpeg = FFmpegTool()
    supabase = SupabaseTool()
    storage = SupabaseStorageTool()
    log = []

    def ts():
        return datetime.datetime.utcnow().strftime('%H:%M:%S')

    rows = supabase.select("content_queue", {"id": content_id}, limit=1)
    if not rows:
        raise ValueError(f"content_id {content_id} not found in content_queue")
    content = rows[0]
    niche = content.get("niche", "rain sounds")
    length_hours = content.get("length_hours", 3)
    duration_s = int(length_hours * 3600)
    job_id = str(uuid.uuid4())[:8]

    SANDBOX.mkdir(parents=True, exist_ok=True)

    supabase.update("content_queue", {"status": "in_production"}, {"id": content_id})
    log.append(f"[{ts()}] INFO  Production Agent starting: {content['title']}")
    log.append(f"[{ts()}] INFO  Niche: {niche} | Duration: {length_hours}h ({duration_s}s)")
    supabase.update_run_log(run_id, log, progress=5)

    # Step 1: Generate thumbnail image with OpenAI gpt-image-1
    thumb_prompt = THUMBNAIL_PROMPTS.get(niche, DEFAULT_THUMB_PROMPT)
    log.append(f"[{ts()}] INFO  Generating thumbnail with gpt-image-1...")
    supabase.update_run_log(run_id, log[-1:], progress=10)
    img_result = openai_tool.generate_image(thumb_prompt, size="1792x1024")
    thumb_local = f"/tmp/thumb_{job_id}.jpg"
    with open(thumb_local, "wb") as f:
        f.write(img_result["image_bytes"])
    thumbnail_url = storage.upload_file(thumb_local, "thumbnails", f"{job_id}_thumb.jpg")
    log.append(f"[{ts()}] INFO  Thumbnail uploaded: {thumbnail_url[:60]}...")
    supabase.update_run_log(run_id, log[-1:], progress=20)

    # Step 2: Get visual loop (auto-downloads if missing)
    log.append(f"[{ts()}] INFO  Fetching visual loop for niche: {niche}")
    supabase.update_run_log(run_id, log[-1:], progress=25)

    def _log_dl(msg: str):
        log.append(f"[{ts()}] INFO  {msg}")
        supabase.update_run_log(run_id, log[-1:], progress=None)

    visual_path = get_visual_path(niche, log_fn=_log_dl)
    log.append(f"[{ts()}] INFO  Visual ready: {Path(visual_path).name}")
    supabase.update_run_log(run_id, log[-1:], progress=35)

    # Step 3: Get audio loop (auto-downloads if missing)
    log.append(f"[{ts()}] INFO  Fetching audio loop for niche: {niche}")
    audio_path = get_audio_path(niche, log_fn=_log_dl)
    log.append(f"[{ts()}] INFO  Audio ready: {Path(audio_path).name}")
    supabase.update_run_log(run_id, log[-1:], progress=50)

    # Step 4: FFmpeg — loop static visual + loop static audio to full duration
    log.append(f"[{ts()}] INFO  FFmpeg render: looping visual + audio to {duration_s}s...")
    supabase.update_run_log(run_id, log[-1:], progress=55)
    output_path = ffmpeg.render(audio_path, visual_path, f"{job_id}_final", duration_s)
    log.append(f"[{ts()}] INFO  Render complete: {output_path}")
    supabase.update_run_log(run_id, log[-1:], progress=80)

    # Step 5: Upload final video to Supabase Storage
    log.append(f"[{ts()}] INFO  Uploading final video to Supabase Storage...")
    video_url = storage.upload_file(output_path, "videos", f"{job_id}.mp4")
    log.append(f"[{ts()}] INFO  Video uploaded: {video_url[:60]}...")
    supabase.update_run_log(run_id, log[-1:], progress=92)

    # Step 6: Update content_queue
    supabase.update("content_queue", {
        "video_url": video_url,
        "audio_url": audio_path,
        "thumbnail_url": thumbnail_url,
        "status": "approved",
    }, {"id": content_id})
    log.append(f"[{ts()}] INFO  content_queue updated — status: approved, all assets set")
    supabase.update_run_log(run_id, log[-1:], progress=100)

    return {
        "summary": f"Production complete for '{content['title']}' — MP4 ready for upload",
        "log": log,
        "result": {"content_id": content_id, "video_url": video_url, "thumbnail_url": thumbnail_url},
        "progress": 100,
    }
