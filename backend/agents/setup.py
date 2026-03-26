"""
Setup Agent — downloads all 13 CC0 visual and audio loops in one run.
Trigger via: POST /api/run-agent  {"agent": "setup"}
Or from the dashboard Agents page.

Requires at least one of:
  PIXABAY_API_KEY   (https://pixabay.com/accounts/register/ — free)
  FREESOUND_API_KEY (https://freesound.org/apiv2/apply/ — free)

If neither key is set, falls back to curated direct download URLs.
"""

import datetime
from tools.supabase_tool import SupabaseTool


def run_setup_agent(run_id: str, input_data: dict) -> dict:
    supabase = SupabaseTool()
    log = []

    def ts():
        return datetime.datetime.utcnow().strftime('%H:%M:%S')

    log.append(f"[{ts()}] INFO  Setup Agent starting — downloading all CC0 assets")
    supabase.update_run_log(run_id, log, progress=2)

    from tools.asset_downloader import download_visual, download_audio
    from agents.production import NICHE_VISUAL_MAP, NICHE_AUDIO_MAP

    all_visuals = {**NICHE_VISUAL_MAP, "default": "default.mp4"}
    all_audios = {**NICHE_AUDIO_MAP, "default": "default.mp3"}
    total = len(all_visuals) + len(all_audios)
    done = 0
    visual_ok, audio_ok, failures = [], [], []

    log.append(f"[{ts()}] INFO  {len(all_visuals)} visuals + {len(all_audios)} audio files = {total} total")
    supabase.update_run_log(run_id, log[-1:], progress=5)

    # Download visuals
    for i, (niche, filename) in enumerate(all_visuals.items()):
        log.append(f"[{ts()}] INFO  Visual {i+1}/{len(all_visuals)}: {filename}")
        supabase.update_run_log(run_id, log[-1:], progress=int(5 + (done / total) * 85))
        try:
            path = download_visual(niche, filename)
            import os
            size_mb = os.path.getsize(path) / 1_048_576
            visual_ok.append(filename)
            log.append(f"[{ts()}] INFO  ✅ {filename} ({size_mb:.1f} MB)")
        except Exception as e:
            failures.append({"file": filename, "error": str(e)})
            log.append(f"[{ts()}] WARN  ❌ {filename}: {str(e)[:100]}")
        done += 1
        supabase.update_run_log(run_id, log[-1:], progress=int(5 + (done / total) * 85))

    # Download audio
    for i, (niche, filename) in enumerate(all_audios.items()):
        log.append(f"[{ts()}] INFO  Audio {i+1}/{len(all_audios)}: {filename}")
        supabase.update_run_log(run_id, log[-1:], progress=int(5 + (done / total) * 85))
        try:
            path = download_audio(niche, filename)
            import os
            size_mb = os.path.getsize(path) / 1_048_576
            audio_ok.append(filename)
            log.append(f"[{ts()}] INFO  ✅ {filename} ({size_mb:.1f} MB)")
        except Exception as e:
            failures.append({"file": filename, "error": str(e)})
            log.append(f"[{ts()}] WARN  ❌ {filename}: {str(e)[:100]}")
        done += 1
        supabase.update_run_log(run_id, log[-1:], progress=int(5 + (done / total) * 85))

    summary = (
        f"Setup complete: {len(visual_ok)}/{len(all_visuals)} visuals, "
        f"{len(audio_ok)}/{len(all_audios)} audio files downloaded"
    )
    if failures:
        summary += f" — {len(failures)} failed (add PIXABAY_API_KEY or FREESOUND_API_KEY to fix)"

    log.append(f"[{ts()}] INFO  {summary}")
    supabase.update_run_log(run_id, log[-1:], progress=100)

    return {
        "summary": summary,
        "log": log,
        "result": {
            "visual_ok": visual_ok,
            "audio_ok": audio_ok,
            "failures": failures,
        },
        "progress": 100,
    }
