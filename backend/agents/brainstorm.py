"""
Brainstorm module — multi-agent discussion round.

Three agents talk to each other to decide the best content angle:
  Round 1 (Research Agent voice):  shares top niches + content gaps
  Round 2 (Strategy Agent voice):  reacts, weighs ROI history, proposes ranked picks
  Round 3 (Content Agent voice):   proposes 3 specific title/angle combos for top pick
  Round 4 (Strategy Agent voice):  scores each proposal, picks winner with reasoning

All turns are stored in `full_output.discussion` so the dashboard can replay the conversation.
"""

import datetime
import json
from tools.openai_tool import OpenAITool
from tools.supabase_tool import SupabaseTool


def run_brainstorm(
    run_id: str,
    research_niches: list[dict],
    niche_decisions: dict,
    channel_metrics: dict,
) -> dict:
    """
    Execute the multi-agent brainstorm session.

    Returns:
        {
          "final_pick": {"niche": str, "angle": str, "length_hours": int, "reasoning": str},
          "discussion": [{"round": int, "agent": str, "message": str}, ...],
        }
    """
    openai = OpenAITool()
    supabase = SupabaseTool()
    discussion: list[dict] = []

    def ts():
        return datetime.datetime.utcnow().strftime('%H:%M:%S')

    def add_turn(agent: str, message: str, round_num: int):
        turn = {"round": round_num, "agent": agent, "ts": ts(), "message": message}
        discussion.append(turn)
        supabase.update_run_log(
            run_id,
            [f"[{ts()}] 💬 {agent.upper()}: {message[:120]}..."],
            progress=None,
        )

    # ───────────────────────────────────────────────
    # Round 1 — Research Agent shares findings
    # ───────────────────────────────────────────────
    top_niches_summary = "\n".join(
        f"  {i+1}. {n['name']} — RPM ${n['rpm_estimate']}, "
        f"competition={n['competition']}, trend={n['trend']}, score={n['score']}"
        f"{(' | gap: ' + n['notes']) if n.get('notes') else ''}"
        for i, n in enumerate(research_niches[:6])
    )

    research_turn = openai.generate_text(f"""
You are the Research Agent on a YouTube ambient/soundscape team.
You just completed trend analysis on 12 niches. Present your findings to the team.

Top niches ranked by score:
{top_niches_summary}

Your job: Present 3-4 key insights from this data. Highlight content gaps and
opportunities the team should act on. Be specific — cite numbers. Keep it to 4-6 sentences.
Write as if speaking to your team in a brainstorm meeting.
""", max_tokens=400)

    add_turn("Research Agent", research_turn, round_num=1)

    # ───────────────────────────────────────────────
    # Round 2 — Strategy Agent weighs in with ROI history
    # ───────────────────────────────────────────────
    exploit_niches = [n for n, d in niche_decisions.items() if d["decision"] == "exploit"]
    kill_niches = [n for n, d in niche_decisions.items() if d["decision"] == "kill"]
    test_niches = [n for n, d in niche_decisions.items() if d["decision"] == "test"]

    channel_context = ""
    if channel_metrics:
        channel_context = (
            f"Channel this week: {channel_metrics.get('total_views', 0):,} views, "
            f"${channel_metrics.get('estimated_revenue', 0):.2f} revenue, "
            f"RPM ${channel_metrics.get('rpm', 0):.2f}"
        )

    strategy_turn = openai.generate_text(f"""
You are the Strategy Agent on a YouTube ambient/soundscape team.
You just heard the Research Agent's findings. Now respond as the strategy brain.

Performance history:
- Proven niches (keep pushing): {exploit_niches if exploit_niches else "none yet — too early"}
- Kill list (stop making): {kill_niches if kill_niches else "none — all still in testing"}
- Still testing: {test_niches if test_niches else "all niches are fresh"}
{channel_context}

Research findings just shared:
"{research_turn[:600]}"

Your job: React to the research. Rank your top 3 niche picks for the NEXT video based on
combining the research scores with what history says. For each pick, give your ROI reasoning.
Be direct — this is a team meeting, not a report. 4-6 sentences.
""", max_tokens=450)

    add_turn("Strategy Agent", strategy_turn, round_num=2)

    # ───────────────────────────────────────────────
    # Round 3 — Content Agent proposes 3 specific video angles
    # ───────────────────────────────────────────────
    content_turn = openai.generate_text(f"""
You are the Content Agent on a YouTube ambient/soundscape team.
You've been listening to Research and Strategy discuss the best niche.

Strategy's top picks: "{strategy_turn[:500]}"

Your job: Propose 3 specific video concepts (title + angle + duration) for what you'd create.
Each concept should be different enough to offer a real choice.

Format as JSON array:
[
  {{
    "title_concept": "evocative title idea",
    "angle": "specific mood/setting angle",
    "length_hours": 3,
    "why": "one sentence on why this angle could win"
  }},
  ...
]

Return ONLY the JSON array. No other text.
""", max_tokens=500)

    try:
        proposals = json.loads(content_turn.strip())
        if not isinstance(proposals, list):
            raise ValueError("not a list")
    except Exception:
        proposals = [
            {"title_concept": "Binaural Beats for Deep Focus — 3 Hours", "angle": "deep work, alpha waves", "length_hours": 3, "why": "High RPM niche with proven retention"},
            {"title_concept": "Dark Forest Ambiance for Night Study — 3 Hours", "angle": "late night forest with rain", "length_hours": 3, "why": "Underserved angle in popular niche"},
            {"title_concept": "8 Hours of Gentle Rain for Deep Sleep", "angle": "sleep, anxiety relief", "length_hours": 8, "why": "Sleep content earns highest RPM"},
        ]

    proposals_formatted = "\n".join(
        f"  {i+1}. \"{p.get('title_concept', '')}\" ({p.get('length_hours', 3)}h) — {p.get('angle', '')} | {p.get('why', '')}"
        for i, p in enumerate(proposals)
    )
    add_turn("Content Agent", f"Here are my 3 proposals:\n{proposals_formatted}", round_num=3)

    # ───────────────────────────────────────────────
    # Round 4 — Strategy Agent picks the winner
    # ───────────────────────────────────────────────
    pick_raw = openai.generate_text(f"""
You are the Strategy Agent. Content Agent just proposed 3 video concepts:

{proposals_formatted}

Business rules:
- RPM floor: skip anything estimated below $8/RPM
- Sleep content gets 8h duration for max watch time
- Proven niches (high retention history): {exploit_niches}
- Kill list: {kill_niches}

Pick the SINGLE best concept. Score each 1-10 on:
  - RPM potential (based on niche)
  - Differentiation from what's already on the channel
  - Viewer demand (search volume / trend direction)

Return ONLY a JSON object:
{{
  "winner_index": 0,
  "niche": "exact niche keyword",
  "angle": "specific angle chosen",
  "length_hours": 3,
  "title_concept": "winning title concept",
  "scores": {{"rpm": 8, "differentiation": 7, "demand": 9}},
  "reasoning": "2-3 sentences explaining your pick"
}}
""", max_tokens=400)

    try:
        pick = json.loads(pick_raw.strip())
        final_pick = {
            "niche": pick.get("niche", research_niches[0]["name"] if research_niches else "rain sounds"),
            "angle": pick.get("angle", "study and focus"),
            "length_hours": int(pick.get("length_hours", 3)),
            "title_concept": pick.get("title_concept", ""),
            "reasoning": pick.get("reasoning", ""),
            "scores": pick.get("scores", {}),
        }
    except Exception:
        final_pick = {
            "niche": research_niches[0]["name"] if research_niches else "binaural beats",
            "angle": "deep focus study session",
            "length_hours": 3,
            "title_concept": "",
            "reasoning": "Fallback: top-ranked niche by research score",
            "scores": {},
        }

    reasoning_msg = (
        f"I'm going with option {pick.get('winner_index', 0) + 1}: "
        f"\"{final_pick['title_concept']}\" ({final_pick['length_hours']}h). "
        f"{final_pick['reasoning']}"
    )
    add_turn("Strategy Agent", reasoning_msg, round_num=4)

    return {
        "final_pick": final_pick,
        "discussion": discussion,
    }
