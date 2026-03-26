"""
Downloads CC0 ambient video loops from Pixabay using yt-dlp.
Run: python3 download_loops.py

Downloads 3–5 variants per niche so the Production Agent never reuses the same loop.
Files are named: {niche}_1.mp4, {niche}_2.mp4, etc.
Existing files are skipped automatically.

Requires: pip install yt-dlp curl_cffi
No API key needed — uses browser impersonation to bypass Cloudflare.
"""

import subprocess
import sys
import os
from pathlib import Path

HERE = Path(__file__).parent

# ─────────────────────────────────────────────────────────────────────────────
# CANDIDATE URLS PER NICHE
# Each list has more candidates than the target count.
# The script tries them in order until it hits the target.
# ─────────────────────────────────────────────────────────────────────────────
NICHES = {
    # (target_count, [candidate_pixabay_urls])

    "rain_sounds": (5, [
        "https://pixabay.com/videos/rain-water-drops-nature-6962/",
        "https://pixabay.com/videos/rain-window-drops-glass-water-45588/",
        "https://pixabay.com/videos/rain-window-drops-nature-rainy-day-4075/",
        "https://pixabay.com/videos/rain-drops-water-window-glass-5342/",
        "https://pixabay.com/videos/rain-drop-water-macro-nature-6027/",
        "https://pixabay.com/videos/rain-puddle-drops-water-storm-8761/",
        "https://pixabay.com/videos/rain-drops-window-glass-water-2891/",
        "https://pixabay.com/videos/rain-water-nature-drops-wet-12047/",
    ]),

    "lofi_study_music": (5, [
        "https://pixabay.com/videos/rain-window-drops-glass-water-45588/",
        "https://pixabay.com/videos/coffee-cafe-table-window-morning-3971/",
        "https://pixabay.com/videos/rain-window-drops-nature-rainy-day-4075/",
        "https://pixabay.com/videos/desk-study-work-notebook-book-3456/",
        "https://pixabay.com/videos/laptop-desk-coffee-work-study-7251/",
        "https://pixabay.com/videos/book-study-read-library-desk-4182/",
        "https://pixabay.com/videos/window-rain-drops-cozy-indoor-9814/",
        "https://pixabay.com/videos/coffee-cup-table-drink-morning-40179/",
    ]),

    "dark_forest_ambiance": (4, [
        "https://pixabay.com/videos/forest-fog-atmospheric-mysterious-1751/",
        "https://pixabay.com/videos/forest-trees-fog-mist-nature-3178/",
        "https://pixabay.com/videos/forest-nature-trees-path-trail-3220/",
        "https://pixabay.com/videos/forest-fog-trees-mist-dark-15492/",
        "https://pixabay.com/videos/trees-forest-nature-fog-misty-7431/",
        "https://pixabay.com/videos/forest-dark-trees-fog-night-2891/",
        "https://pixabay.com/videos/forest-fog-atmospheric-nature-9127/",
    ]),

    "coffee_shop_ambiance": (3, [
        "https://pixabay.com/videos/coffee-cup-table-drink-morning-40179/",
        "https://pixabay.com/videos/coffee-cafe-table-window-morning-3971/",
        "https://pixabay.com/videos/coffee-shop-cafe-interior-cozy-5201/",
        "https://pixabay.com/videos/coffee-espresso-cup-drink-cafe-6781/",
        "https://pixabay.com/videos/coffee-cup-morning-drink-table-8942/",
    ]),

    "fireplace_crackle": (4, [
        "https://pixabay.com/videos/fire-fireplace-logs-burning-2094/",
        "https://pixabay.com/videos/fireplace-fire-wood-burning-warm-27072/",
        "https://pixabay.com/videos/fire-flames-burning-fireplace-cozy-4581/",
        "https://pixabay.com/videos/campfire-fire-flames-burning-night-9203/",
        "https://pixabay.com/videos/fire-flame-burning-wood-logs-3917/",
        "https://pixabay.com/videos/fireplace-fire-hearth-warm-cozy-11047/",
    ]),

    "thunderstorm_sounds": (3, [
        "https://pixabay.com/videos/lightning-storm-thunder-clouds-sky-30866/",
        "https://pixabay.com/videos/storm-rain-lightning-nature-sky-1850/",
        "https://pixabay.com/videos/storm-lightning-thunder-dark-clouds-18293/",
        "https://pixabay.com/videos/lightning-storm-clouds-thunder-rain-6042/",
        "https://pixabay.com/videos/storm-clouds-lightning-rain-dark-9571/",
    ]),

    "binaural_beats": (3, [
        "https://pixabay.com/videos/particles-abstract-motion-glow-1867/",
        "https://pixabay.com/videos/aurora-borealis-night-sky-lights-10268/",
        "https://pixabay.com/videos/space-stars-galaxy-universe-dark-2152/",
        "https://pixabay.com/videos/particles-abstract-blue-glow-wave-3419/",
        "https://pixabay.com/videos/aurora-northern-lights-sky-night-7831/",
    ]),

    "sleep_sounds_anxiety": (3, [
        "https://pixabay.com/videos/ocean-sea-waves-water-beach-1386/",
        "https://pixabay.com/videos/sea-ocean-waves-water-beach-4078/",
        "https://pixabay.com/videos/ocean-waves-water-sea-beach-6553/",
        "https://pixabay.com/videos/sea-waves-beach-ocean-sunset-water-3812/",
        "https://pixabay.com/videos/ocean-calm-water-waves-sea-night-9034/",
    ]),

    "nature_asmr": (3, [
        "https://pixabay.com/videos/nature-forest-trees-path-sunlight-7178/",
        "https://pixabay.com/videos/forest-nature-trees-path-trail-3220/",
        "https://pixabay.com/videos/forest-nature-morning-birds-path-7197/",
        "https://pixabay.com/videos/nature-plants-green-sunlight-forest-5841/",
        "https://pixabay.com/videos/forest-sunlight-nature-trees-green-4219/",
    ]),

    "white_noise": (3, [
        "https://pixabay.com/videos/fog-mist-morning-nature-lake-3261/",
        "https://pixabay.com/videos/fog-mist-nature-morning-lake-7192/",
        "https://pixabay.com/videos/fog-mist-forest-trees-nature-4817/",
        "https://pixabay.com/videos/mist-fog-nature-lake-morning-calm-9341/",
    ]),

    "ocean_waves_sleep": (5, [
        "https://pixabay.com/videos/sea-waves-ocean-water-beach-1049/",
        "https://pixabay.com/videos/ocean-sea-waves-water-beach-1386/",
        "https://pixabay.com/videos/sea-ocean-waves-water-beach-4078/",
        "https://pixabay.com/videos/ocean-waves-water-sea-beach-6553/",
        "https://pixabay.com/videos/sea-waves-beach-ocean-sunset-water-3812/",
        "https://pixabay.com/videos/ocean-waves-beach-water-sea-night-11429/",
        "https://pixabay.com/videos/ocean-sea-waves-shore-beach-calm-8291/",
    ]),

    "forest_birds_morning": (3, [
        "https://pixabay.com/videos/forest-nature-morning-birds-path-7197/",
        "https://pixabay.com/videos/forest-nature-trees-path-sunlight-7178/",
        "https://pixabay.com/videos/forest-nature-trees-birds-3187/",
        "https://pixabay.com/videos/forest-morning-sunlight-trees-birds-5193/",
        "https://pixabay.com/videos/nature-forest-birds-morning-trees-8024/",
    ]),
}

# Placeholder colors used if all Pixabay downloads fail for a niche
PLACEHOLDER_COLORS = {
    "rain_sounds":          ("0x1a2a3a", "dark blue-grey"),
    "lofi_study_music":     ("0x2a1a0a", "warm amber"),
    "dark_forest_ambiance": ("0x0a1a0a", "dark green"),
    "coffee_shop_ambiance": ("0x2a1a10", "warm brown"),
    "fireplace_crackle":    ("0x3a1a00", "deep orange"),
    "thunderstorm_sounds":  ("0x10141a", "storm grey"),
    "binaural_beats":       ("0x0a0a2a", "deep purple"),
    "sleep_sounds_anxiety": ("0x0a1a2a", "midnight blue"),
    "nature_asmr":          ("0x0a1f0a", "forest green"),
    "white_noise":          ("0x1a1a1a", "light grey"),
    "ocean_waves_sleep":    ("0x001a2a", "deep ocean"),
    "forest_birds_morning": ("0x1a2a0a", "morning green"),
}

YTDLP = [sys.executable, "-m", "yt_dlp"]


def try_download(url: str, out: Path) -> bool:
    cmd = [
        *YTDLP,
        "--impersonate", "chrome",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", str(out),
        "--no-playlist",
        "--quiet",
        "--progress",
        url,
    ]
    result = subprocess.run(cmd)
    ok = result.returncode == 0 and out.exists() and out.stat().st_size > 50_000
    if not ok and out.exists():
        out.unlink()
    return ok


def make_ffmpeg_placeholder(out: Path, color: str, label: str) -> bool:
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:size=1920x1080:rate=30,hue=h=t*5,eq=brightness=0.05:contrast=1.1",
        "-t", "30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "28", "-pix_fmt", "yuv420p",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0 and out.exists()


def main():
    os.chdir(HERE)
    totals = {"downloaded": 0, "skipped": 0, "placeholder": 0, "failed": 0}

    for niche, (target, candidates) in NICHES.items():
        print(f"\n{'─'*60}")
        print(f"📁  {niche}  (target: {target} variants)")

        # Find which variant indices are still needed
        existing = sorted(HERE.glob(f"{niche}_*.mp4"))
        done = len(existing)
        if done >= target:
            print(f"   ✅ Already have {done}/{target} — skipping")
            totals["skipped"] += done
            continue

        # Figure out where to start numbering
        used_urls = set()
        variant_idx = done + 1

        for url in candidates:
            if variant_idx > target:
                break
            if url in used_urls:
                continue
            used_urls.add(url)

            out = HERE / f"{niche}_{variant_idx}.mp4"
            if out.exists() and out.stat().st_size > 50_000:
                size_mb = out.stat().st_size / 1_048_576
                print(f"   ✅ {out.name} exists ({size_mb:.1f} MB)")
                variant_idx += 1
                totals["skipped"] += 1
                continue

            print(f"   ⬇  [{variant_idx}/{target}] {url.split('/')[-2]}")
            if try_download(url, out):
                size_mb = out.stat().st_size / 1_048_576
                print(f"   ✅ {out.name} ({size_mb:.1f} MB)")
                variant_idx += 1
                totals["downloaded"] += 1
            else:
                print(f"   ✗  Failed — trying next candidate")

        # If we still haven't hit target, fill with FFmpeg placeholders
        color, label = PLACEHOLDER_COLORS.get(niche, ("0x1a2a3a", "default"))
        while variant_idx <= target:
            out = HERE / f"{niche}_{variant_idx}.mp4"
            print(f"   ⚠️  [{variant_idx}/{target}] Generating FFmpeg placeholder ({label})")
            if make_ffmpeg_placeholder(out, color, label):
                size_mb = out.stat().st_size / 1_048_576
                print(f"   ⚠️  {out.name} generated ({size_mb:.1f} MB) — replace with real footage")
                totals["placeholder"] += 1
            else:
                print(f"   ❌ {out.name} FAILED")
                totals["failed"] += 1
            variant_idx += 1

    # Also write a default.mp4 that points to rain_sounds_1
    default = HERE / "default.mp4"
    rain1 = HERE / "rain_sounds_1.mp4"
    if not default.exists() and rain1.exists():
        import shutil
        shutil.copy2(rain1, default)
        print(f"\n✅ default.mp4 → copied from rain_sounds_1.mp4")

    print(f"\n{'═'*60}")
    total_files = sum(totals.values())
    print(f"✅ Downloaded:   {totals['downloaded']}")
    print(f"⏭  Skipped:      {totals['skipped']}")
    print(f"⚠️  Placeholders: {totals['placeholder']}")
    print(f"❌ Failed:       {totals['failed']}")
    print(f"📦 Total files:  {total_files}")
    print(f"{'═'*60}")

    # List final state
    print("\nFinal visuals/ directory:")
    for f in sorted(HERE.glob("*.mp4")):
        size_mb = f.stat().st_size / 1_048_576
        print(f"  {f.name:<40} {size_mb:>6.1f} MB")


if __name__ == "__main__":
    main()
