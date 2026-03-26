"""
Downloads CC0 ambient audio loops from Freesound.org using yt-dlp.
Run: python3 download_loops.py

- Scrapes Freesound search results (no API key needed)
- Downloads 3 variants per niche named {niche}_1.mp3, {niche}_2.mp3, etc.
- Existing files are skipped automatically
- Falls back to known working IDs if scraping fails

Requires: pip install yt-dlp curl_cffi
"""

import subprocess
import sys
import os
import re
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent

# ─── Search queries per niche → (target_count, freesound_search_query) ───────
NICHES = {
    "rain_sounds":          (3, "rain ambience loop seamless"),
    "lofi_study_music":     (3, "lo-fi chill study music loop"),
    "dark_forest_ambiance": (3, "dark forest night ambience loop"),
    "coffee_shop_ambiance": (3, "cafe coffee shop ambience loop"),
    "fireplace_crackle":    (3, "fireplace crackling fire loop"),
    "thunderstorm_sounds":  (3, "thunderstorm rain loop"),
    "binaural_beats":       (3, "binaural beats meditation loop"),
    "sleep_sounds_anxiety": (3, "ocean waves sleep loop"),
    "nature_asmr":          (3, "nature forest birds asmr loop"),
    "white_noise":          (3, "white noise loop seamless"),
    "ocean_waves_sleep":    (3, "ocean waves beach night loop"),
    "forest_birds_morning": (3, "morning birds forest dawn loop"),
}

# ─── Fallback known-good Freesound IDs (confirmed CC0) ───────────────────────
# Used when scraping can't find enough results.
FALLBACK_IDS = {
    "rain_sounds":          ["217506", "242889", "177479"],
    "lofi_study_music":     ["242889", "525046", "423610"],
    "dark_forest_ambiance": ["30936",  "535870", "679176"],
    "coffee_shop_ambiance": ["525046", "535869", "728429"],
    "fireplace_crackle":    ["535868", "30936",  "177479"],
    "thunderstorm_sounds":  ["242889", "728429", "535870"],
    "binaural_beats":       ["679176", "423610", "217506"],
    "sleep_sounds_anxiety": ["177479", "242889", "30936" ],
    "nature_asmr":          ["535869", "679176", "525046"],
    "white_noise":          ["535870", "535868", "728429"],
    "ocean_waves_sleep":    ["242889", "177479", "535869"],
    "forest_birds_morning": ["30936",  "525046", "423610"],
}

YTDLP = [sys.executable, "-m", "yt_dlp"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def scrape_freesound_ids(query: str, limit: int = 10) -> list[str]:
    """Scrape Freesound search results for CC0 sounds, sorted by downloads."""
    q = urllib.parse.quote_plus(query)
    url = (
        f"https://freesound.org/search/"
        f"?q={q}"
        f"&f=license%3A%22Creative+Commons+0%22"
        f"&s=num_downloads+desc"
        f"&only_p=0"
    )
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=15).read().decode(errors="ignore")
        ids = re.findall(r'/sounds/(\d+)/', html)
        return list(dict.fromkeys(ids))[:limit]  # unique, preserve order
    except Exception as e:
        print(f"   ⚠  Scrape failed: {e}")
        return []


def try_download(sound_id: str, out: Path) -> bool:
    """Download a Freesound sound by ID using yt-dlp. Returns True on success."""
    url = f"https://freesound.org/s/{sound_id}/"
    cmd = [
        *YTDLP,
        "--impersonate", "chrome",
        "-x",                          # extract audio only
        "--audio-format", "mp3",
        "--audio-quality", "0",        # best quality
        "-o", str(out.with_suffix("")),  # yt-dlp adds .mp3 itself
        "--no-playlist",
        "--quiet",
        "--progress",
        url,
    ]
    result = subprocess.run(cmd)
    # yt-dlp may save as .mp3 even if we omit extension
    candidate = out if out.exists() else out.with_suffix(".mp3")
    ok = result.returncode == 0 and candidate.exists() and candidate.stat().st_size > 20_000
    if not ok:
        for p in [out, candidate]:
            if p.exists():
                p.unlink()
    elif candidate != out:
        candidate.rename(out)
    return ok


def main():
    import urllib.parse  # noqa

    os.chdir(HERE)
    totals = {"downloaded": 0, "skipped": 0, "failed": 0}

    for niche, (target, query) in NICHES.items():
        print(f"\n{'─'*60}")
        print(f"🎵  {niche}  (target: {target} variants)")

        # Count already-complete variants
        existing = sorted(HERE.glob(f"{niche}_*.mp3"))
        done = len(existing)
        if done >= target:
            print(f"   ✅ Already have {done}/{target} — skipping")
            totals["skipped"] += done
            continue

        variant_idx = done + 1

        # Scrape IDs from Freesound
        print(f"   🔍 Searching Freesound for: \"{query}\"")
        scraped_ids = scrape_freesound_ids(query, limit=15)
        fallback_ids = FALLBACK_IDS.get(niche, [])
        # Merge: scraped first, then fallbacks, deduplicated
        all_ids = list(dict.fromkeys(scraped_ids + fallback_ids))
        print(f"   Found {len(scraped_ids)} results + {len(fallback_ids)} fallback IDs")

        for sound_id in all_ids:
            if variant_idx > target:
                break
            out = HERE / f"{niche}_{variant_idx}.mp3"
            if out.exists() and out.stat().st_size > 20_000:
                size_mb = out.stat().st_size / 1_048_576
                print(f"   ✅ {out.name} exists ({size_mb:.1f} MB)")
                variant_idx += 1
                totals["skipped"] += 1
                continue

            print(f"   ⬇  [{variant_idx}/{target}] freesound.org/s/{sound_id}/")
            if try_download(sound_id, out):
                size_mb = out.stat().st_size / 1_048_576
                print(f"   ✅ {out.name} ({size_mb:.2f} MB)")
                variant_idx += 1
                totals["downloaded"] += 1
            else:
                print(f"   ✗  ID {sound_id} failed — trying next")
            time.sleep(0.5)  # be polite to Freesound

        if variant_idx <= target:
            print(f"   ❌ Only got {variant_idx - 1}/{target} for {niche}")
            totals["failed"] += (target - variant_idx + 1)

    # Copy default.mp3 from rain_sounds_1 if needed
    default = HERE / "default.mp3"
    rain1 = HERE / "rain_sounds_1.mp3"
    if not default.exists() and rain1.exists():
        import shutil
        shutil.copy2(rain1, default)
        print(f"\n✅ default.mp3 → copied from rain_sounds_1.mp3")

    print(f"\n{'═'*60}")
    print(f"✅ Downloaded:  {totals['downloaded']}")
    print(f"⏭  Skipped:     {totals['skipped']}")
    print(f"❌ Failed:      {totals['failed']}")
    print(f"{'═'*60}")

    print("\nFinal audio/ directory:")
    for f in sorted(HERE.glob("*.mp3")):
        size_mb = f.stat().st_size / 1_048_576
        print(f"  {f.name:<42} {size_mb:>5.2f} MB")


if __name__ == "__main__":
    main()
