import datetime
import json
from tools.openai_tool import OpenAITool
from tools.youtube_search import YouTubeSearchTool
from tools.supabase_tool import SupabaseTool

TARGET_NICHES = [
    "rain sounds", "lo-fi study music", "dark forest ambiance",
    "coffee shop ambiance", "fireplace crackle", "thunderstorm sounds",
    "binaural beats", "sleep sounds anxiety", "nature ASMR", "white noise",
    "ocean waves sleep", "forest birds morning",
]

RPM_TABLE = {
    "rain sounds": 9.2, "lo-fi study music": 11.4, "dark forest ambiance": 9.1,
    "coffee shop ambiance": 10.2, "fireplace crackle": 8.9, "thunderstorm sounds": 8.5,
    "binaural beats": 12.0, "sleep sounds anxiety": 8.8, "nature ASMR": 9.5,
    "white noise": 8.3, "ocean waves sleep": 8.7, "forest birds morning": 9.0,
}


def run_research_agent(run_id: str, input_data: dict) -> dict:
    openai_tool = OpenAITool()
    youtube = YouTubeSearchTool()
    supabase = SupabaseTool()
    log = []

    def ts():
        return datetime.datetime.utcnow().strftime('%H:%M:%S')

    niches_to_scan = input_data.get("niches", TARGET_NICHES)
    log.append(f"[{ts()}] INFO  Research Agent starting — {len(niches_to_scan)} niches to scan")
    supabase.update_run_log(run_id, log, progress=5)

    # Step 1: Perplexity research sweep — get trend/competition intel for all niches at once
    log.append(f"[{ts()}] INFO  Querying OpenAI web search for YouTube ambient niche trends...")
    supabase.update_run_log(run_id, log[-1:], progress=10)

    niche_list = ", ".join(niches_to_scan)
    research_prompt = f"""
You are a YouTube channel analyst with expertise in ambient/soundscape content.
Research these niches for a YouTube channel in 2026:
{niche_list}

For each niche, apply the content gap analysis framework:
1. Trend direction (growing / stable / declining) — what's happening with search volume?
2. Competition level (high / medium / low) — how saturated is YouTube in this niche?
3. Content gap rating (⭐⭐⭐ high / ⭐⭐ medium / ⭐ low) — is there an underserved angle?
4. Notes — the specific underserved angle or opportunity, if any (e.g. "8-hour sleep versions are rare", "dark aesthetic missing from top results")

Return a JSON object where each key is the exact niche name from the list:
{{
  "niche name": {{
    "trend": "growing|stable|declining",
    "competition": "high|medium|low",
    "gap_rating": "high|medium|low",
    "notes": "specific angle opportunity or observation"
  }}
}}

Focus on actionable insights — not data dumping. Back each gap with a specific reason.
"""
    try:
        research_raw = openai_tool.research(research_prompt)
        # Extract JSON from response
        start = research_raw.find('{')
        end = research_raw.rfind('}') + 1
        research_data = json.loads(research_raw[start:end]) if start != -1 else {}
        log.append(f"[{ts()}] INFO  OpenAI research complete — data for {len(research_data)} niches")
    except Exception as e:
        log.append(f"[{ts()}] WARN  OpenAI research failed ({e}), using defaults")
        research_data = {}

    supabase.update_run_log(run_id, log[-1:], progress=40)

    # Step 2: Per-niche scoring using research data + YouTube competition check
    results = []
    for i, niche in enumerate(niches_to_scan):
        log.append(f"[{ts()}] INFO  Scoring niche {i+1}/{len(niches_to_scan)}: {niche}")
        supabase.update_run_log(run_id, log[-1:], progress=int(40 + (i / len(niches_to_scan)) * 50))

        niche_data = research_data.get(niche, {})
        trend = niche_data.get("trend", "stable")
        competition = niche_data.get("competition", "medium")
        gap_rating = niche_data.get("gap_rating", "medium")

        # YouTube competition cross-check via free API
        try:
            yt_results = youtube.search(niche, max_results=10)
            video_ids = [r["id"].get("videoId") for r in yt_results if r["id"].get("videoId")]
            stats = youtube.video_stats(video_ids) if video_ids else []
            high_view = sum(1 for s in stats if int(s.get("statistics", {}).get("viewCount", 0)) > 1_000_000)
            if high_view >= 8:
                competition = "high"
            elif high_view >= 4:
                competition = "medium"
            else:
                competition = "low"
        except Exception as e:
            log.append(f"[{ts()}] WARN  YouTube check failed for '{niche}': {e}")

        rpm = RPM_TABLE.get(niche, 9.0)
        rpm_score = min((rpm - 7.0) / 6.0, 1.0)
        competition_score = {"high": 0.3, "medium": 0.6, "low": 1.0}.get(competition, 0.5)
        trend_score = {"growing": 1.0, "stable": 0.5, "declining": 0.2}.get(trend, 0.5)
        # Content gap bonus: ⭐⭐⭐ high gap = significant boost (more opportunity)
        gap_score = {"high": 1.0, "medium": 0.5, "low": 0.2}.get(gap_rating, 0.5)
        score = round((rpm_score * 0.35 + competition_score * 0.30 + trend_score * 0.20 + gap_score * 0.15) * 100)

        results.append({
            "name": niche,
            "rpm_estimate": rpm,
            "competition": competition,
            "trend": trend,
            "gap_rating": gap_rating,
            "score": score,
            "notes": niche_data.get("notes", ""),
        })
        gap_star = {"high": "⭐⭐⭐", "medium": "⭐⭐", "low": "⭐"}.get(gap_rating, "⭐⭐")
        log.append(f"[{ts()}] INFO  {niche}: RPM ${rpm}, competition={competition}, trend={trend}, gap={gap_star}, score={score}")

    results.sort(key=lambda x: x["score"], reverse=True)
    log.append(f"[{ts()}] INFO  Research complete. Top: {results[0]['name']} (score {results[0]['score']})")
    supabase.update_run_log(run_id, log[-1:], progress=100)

    return {
        "summary": f"Scanned {len(results)} niches. Top: {results[0]['name']} (RPM ${results[0]['rpm_estimate']}, score {results[0]['score']})",
        "log": log,
        "result": {"niches": results},
        "progress": 100,
    }
