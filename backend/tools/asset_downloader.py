"""
Asset downloader — automatically fetches CC0 visual loops and audio loops
when the Production Agent finds a file missing.

Sources:
  Visuals: Pixabay Video API (free key, CC0 license)
  Audio:   Freesound.org API (free key, CC0 filter)

Both APIs require a free API key:
  PIXABAY_API_KEY  → https://pixabay.com/accounts/register/
  FREESOUND_API_KEY → https://freesound.org/apiv2/apply/

If a key is missing we fall back to a curated list of direct CC0 download URLs
that work without any API key.
"""

import os
import httpx
from pathlib import Path

VISUALS_DIR = Path(__file__).parent.parent / "visuals"
AUDIO_DIR = Path(__file__).parent.parent / "audio"

# ─── Pixabay search queries per niche ────────────────────────────────────────
VISUAL_QUERIES = {
    "rain sounds":          "rain nature falling",
    "lo-fi study music":    "cozy room night window rain",
    "dark forest ambiance": "dark forest night fog",
    "coffee shop ambiance": "coffee shop cafe interior",
    "fireplace crackle":    "fireplace fire crackling",
    "thunderstorm sounds":  "storm lightning rain",
    "binaural beats":       "abstract aurora meditation",
    "sleep sounds anxiety": "ocean waves night calm",
    "nature ASMR":          "forest sunlight nature peaceful",
    "white noise":          "fog mist abstract calm",
    "ocean waves sleep":    "ocean beach night waves",
    "forest birds morning": "forest morning sunrise birds",
    "default":              "nature peaceful ambient",
}

# ─── Freesound search queries per niche ──────────────────────────────────────
AUDIO_QUERIES = {
    "rain sounds":          "rain ambient loop",
    "lo-fi study music":    "lofi music ambient",
    "dark forest ambiance": "forest night ambient",
    "coffee shop ambiance": "cafe coffee shop ambiance",
    "fireplace crackle":    "fireplace crackling loop",
    "thunderstorm sounds":  "thunderstorm rain loop",
    "binaural beats":       "binaural beats focus",
    "sleep sounds anxiety": "sleep calm ambient",
    "nature ASMR":          "nature forest birds",
    "white noise":          "white noise ambient",
    "ocean waves sleep":    "ocean waves loop",
    "forest birds morning": "forest morning birds",
    "default":              "ambient nature loop",
}

# ─── Fallback direct CC0 URLs (no API key needed) ────────────────────────────
# These are stable Pixabay / Freesound direct links for the most important niches.
# If Pixabay/Freesound APIs fail, we download these instead.
FALLBACK_VISUAL_URLS = {
    "rain_sounds.mp4":          "https://cdn.pixabay.com/video/2016/12/30/6962-197634550_tiny.mp4",
    "lofi_study_music.mp4":     "https://cdn.pixabay.com/video/2021/05/18/73996-552673912_tiny.mp4",
    "dark_forest_ambiance.mp4": "https://cdn.pixabay.com/video/2020/08/13/47201-450336836_tiny.mp4",
    "coffee_shop_ambiance.mp4": "https://cdn.pixabay.com/video/2021/10/07/91305-627003185_tiny.mp4",
    "fireplace_crackle.mp4":    "https://cdn.pixabay.com/video/2016/02/18/2094-156140151_tiny.mp4",
    "thunderstorm_sounds.mp4":  "https://cdn.pixabay.com/video/2022/09/27/132892-755380800_tiny.mp4",
    "binaural_beats.mp4":       "https://cdn.pixabay.com/video/2021/08/09/84169-583627847_tiny.mp4",
    "sleep_sounds_anxiety.mp4": "https://cdn.pixabay.com/video/2020/07/09/44993-437096984_tiny.mp4",
    "nature_asmr.mp4":          "https://cdn.pixabay.com/video/2020/05/13/39207-420907575_tiny.mp4",
    "white_noise.mp4":          "https://cdn.pixabay.com/video/2021/03/15/68003-524025702_tiny.mp4",
    "ocean_waves_sleep.mp4":    "https://cdn.pixabay.com/video/2020/07/28/45870-443089447_tiny.mp4",
    "forest_birds_morning.mp4": "https://cdn.pixabay.com/video/2020/06/03/40553-427277027_tiny.mp4",
    "default.mp4":              "https://cdn.pixabay.com/video/2016/12/30/6962-197634550_tiny.mp4",
}


def _download_file(url: str, dest: Path, label: str) -> bool:
    """Download a file from URL to dest. Returns True on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)
        size_mb = dest.stat().st_size / 1_048_576
        print(f"[asset_downloader] ✅ {label} → {dest.name} ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"[asset_downloader] ❌ Failed to download {label}: {e}")
        if dest.exists():
            dest.unlink()
        return False


def download_visual(niche: str, filename: str) -> str:
    """
    Download a CC0 ambient visual loop for the given niche.
    Returns the local file path on success.
    Raises RuntimeError if all methods fail.
    """
    dest = VISUALS_DIR / filename
    if dest.exists() and dest.stat().st_size > 10_000:
        return str(dest)

    VISUALS_DIR.mkdir(parents=True, exist_ok=True)
    api_key = os.getenv("PIXABAY_API_KEY", "")
    query = VISUAL_QUERIES.get(niche, VISUAL_QUERIES["default"])

    # Try Pixabay API first
    if api_key:
        try:
            r = httpx.get(
                "https://pixabay.com/api/videos/",
                params={"key": api_key, "q": query, "video_type": "film", "per_page": 5, "safesearch": "true"},
                timeout=30,
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            for hit in hits:
                # Prefer medium quality, fall back to tiny
                videos = hit.get("videos", {})
                url = (
                    videos.get("medium", {}).get("url")
                    or videos.get("small", {}).get("url")
                    or videos.get("tiny", {}).get("url")
                )
                if url and _download_file(url, dest, f"visual:{niche}"):
                    return str(dest)
        except Exception as e:
            print(f"[asset_downloader] Pixabay API error: {e} — trying fallback")

    # Fallback to curated direct URLs
    fallback_url = FALLBACK_VISUAL_URLS.get(filename, FALLBACK_VISUAL_URLS["default.mp4"])
    if _download_file(fallback_url, dest, f"visual:{niche} (fallback)"):
        return str(dest)

    raise RuntimeError(
        f"Could not download visual for '{niche}'. "
        f"Add PIXABAY_API_KEY to backend/.env (free at pixabay.com/accounts/register/) "
        f"or manually place {filename} in backend/visuals/."
    )


def download_audio(niche: str, filename: str) -> str:
    """
    Download a CC0 ambient audio loop for the given niche.
    Returns the local file path on success.
    Raises RuntimeError if all methods fail.
    """
    dest = AUDIO_DIR / filename
    if dest.exists() and dest.stat().st_size > 10_000:
        return str(dest)

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    api_key = os.getenv("FREESOUND_API_KEY", "")
    query = AUDIO_QUERIES.get(niche, AUDIO_QUERIES["default"])

    # Try Freesound API
    if api_key:
        try:
            # Search for CC0 loopable sounds
            r = httpx.get(
                "https://freesound.org/apiv2/search/text/",
                params={
                    "token": api_key,
                    "query": query,
                    "filter": "license:\"Creative Commons 0\" duration:[60 TO 600]",
                    "sort": "downloads_desc",
                    "fields": "id,name,previews,download",
                    "page_size": 5,
                },
                timeout=30,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            for sound in results:
                # Use the HQ preview (mp3) — it's accessible without OAuth
                preview_url = sound.get("previews", {}).get("preview-hq-mp3")
                if preview_url:
                    # Freesound previews need the API token
                    preview_url_with_token = f"{preview_url}?token={api_key}"
                    # Save as mp3 first, then rename
                    mp3_dest = dest.with_suffix(".mp3") if dest.suffix != ".mp3" else dest
                    if _download_file(preview_url_with_token, mp3_dest, f"audio:{niche}"):
                        return str(mp3_dest)
        except Exception as e:
            print(f"[asset_downloader] Freesound API error: {e} — trying Pixabay music")

    # Fall back to Pixabay music API
    pixabay_key = os.getenv("PIXABAY_API_KEY", "")
    if pixabay_key:
        try:
            r = httpx.get(
                "https://pixabay.com/api/",
                params={
                    "key": pixabay_key,
                    "q": query.replace("loop", "").replace("ambient", ""),
                    "category": "music",
                    "per_page": 5,
                    "safesearch": "true",
                },
                timeout=30,
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            for hit in hits:
                url = hit.get("previewURL") or hit.get("largeImageURL")
                if url and url.endswith(".mp3"):
                    if _download_file(url, dest, f"audio:{niche} (Pixabay)"):
                        return str(dest)
        except Exception as e:
            print(f"[asset_downloader] Pixabay music error: {e}")

    raise RuntimeError(
        f"Could not download audio for '{niche}'. "
        f"Add FREESOUND_API_KEY to backend/.env (free at freesound.org/apiv2/apply/) "
        f"or PIXABAY_API_KEY, "
        f"or manually place {filename} in backend/audio/."
    )


def ensure_all_assets(log_fn=print) -> dict:
    """
    Download at least 1 visual and audio loop per niche if none exist yet.
    The production agent picks randomly from all variants at render time.
    For full multi-variant download, run: python3 backend/visuals/download_loops.py
    """
    from agents.production import NICHE_VISUAL_MAP, NICHE_AUDIO_MAP  # noqa: avoid circular
    results = {"visual_ok": [], "audio_ok": [], "visual_fail": [], "audio_fail": []}

    for niche, prefix in NICHE_VISUAL_MAP.items():
        # Check if any variant exists already
        existing = list(VISUALS_DIR.glob(f"{prefix}_*.mp4")) + list(VISUALS_DIR.glob(f"{prefix}.mp4"))
        if existing:
            results["visual_ok"].append(niche)
            log_fn(f"✅ Visual ready: {prefix} ({len(existing)} variant(s))")
            continue
        try:
            download_visual(niche, f"{prefix}_1.mp4")
            results["visual_ok"].append(niche)
            log_fn(f"✅ Visual downloaded: {prefix}_1.mp4")
        except Exception as e:
            results["visual_fail"].append({"niche": niche, "error": str(e)})
            log_fn(f"❌ Visual failed: {prefix} — {e}")

    for niche, prefix in NICHE_AUDIO_MAP.items():
        existing = list(AUDIO_DIR.glob(f"{prefix}_*.mp3")) + list(AUDIO_DIR.glob(f"{prefix}.mp3"))
        if existing:
            results["audio_ok"].append(niche)
            log_fn(f"✅ Audio ready: {prefix} ({len(existing)} variant(s))")
            continue
        try:
            download_audio(niche, f"{prefix}_1.mp3")
            results["audio_ok"].append(niche)
            log_fn(f"✅ Audio downloaded: {prefix}_1.mp3")
        except Exception as e:
            results["audio_fail"].append({"niche": niche, "error": str(e)})
            log_fn(f"❌ Audio failed: {prefix} — {e}")

    return results
