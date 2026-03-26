import datetime
import json
import uuid as _uuid
from tools.openai_tool import OpenAITool
from tools.supabase_tool import SupabaseTool
from tools.supabase_storage import SupabaseStorageTool

TITLE_PATTERNS = [
    '"X Hours of Y" (e.g. "3 Hours of Deep Forest Rain")',
    '"Cozy [Setting] Ambiance" (e.g. "Cozy Coffee Shop Ambiance")',
    '"[Setting] Sounds for Sleep/Study/Focus"',
    '"Dark/Deep [Setting] for Focus/Work"',
    '"[Duration] [Setting] — No Ads, No Interruptions"',
    '"Study With Me: [Duration] of [Setting]"',
]

# SEO keyword clusters per niche (informed by seo-content-writer skill)
NICHE_KEYWORDS: dict[str, list[str]] = {
    "rain sounds":         ["rain sounds for sleeping", "rain sounds for studying", "relaxing rain"],
    "lo-fi study music":   ["lofi hip hop", "study music", "lo-fi beats to relax"],
    "dark forest ambiance": ["dark forest sounds", "forest ambiance night", "mystical forest"],
    "coffee shop ambiance": ["coffee shop sounds", "cafe ambiance", "coffee shop study music"],
    "fireplace crackle":   ["fireplace sounds", "crackling fire", "cozy fireplace"],
    "thunderstorm sounds": ["thunderstorm rain", "rain and thunder", "storm sounds for sleep"],
    "binaural beats":      ["binaural beats focus", "40hz gamma waves", "binaural beats study"],
    "sleep sounds anxiety": ["sleep sounds anxiety", "calming sounds for anxiety", "sleep meditation"],
    "nature ASMR":         ["nature asmr", "forest asmr", "bird sounds morning"],
    "white noise":         ["white noise for sleep", "white noise baby", "white noise concentration"],
    "ocean waves sleep":   ["ocean waves sleep", "ocean sounds relaxing", "beach sounds sleeping"],
    "forest birds morning": ["birds chirping morning", "forest morning sounds", "nature birds"],
}


def run_content_agent(run_id: str, input_data: dict) -> dict:
    niche = input_data.get("niche", "rain sounds")
    angle = input_data.get("angle", "study and focus")
    length_hours = input_data.get("length_hours", 3)
    title_concept = input_data.get("title_concept", "")  # hint from brainstorm

    openai_tool = OpenAITool()
    supabase = SupabaseTool()
    storage = SupabaseStorageTool()
    log = []

    def ts():
        return datetime.datetime.utcnow().strftime('%H:%M:%S')

    # Step 1: Generate title variants (with SEO scoring from seo-content-writer skill)
    seo_keywords = NICHE_KEYWORDS.get(niche, [niche, f"{niche} sounds", f"relaxing {niche}"])
    concept_hint = f"\nBrainstorm suggested concept: \"{title_concept}\"" if title_concept else ""
    log.append(f"[{ts()}] INFO  Generating SEO-optimised title variants for: {niche} / {angle}")
    supabase.update_run_log(run_id, log[-1:], progress=10)

    titles_raw = openai_tool.generate_text(f"""
Generate 3 YouTube video title variants for an ambient/soundscape video.
Niche: {niche}
Angle/mood: {angle}
Duration: {length_hours} hours
Top search keywords to work in: {', '.join(seo_keywords[:3])}{concept_hint}

Title patterns to draw from: {', '.join(TITLE_PATTERNS)}

Rules:
- Include the duration ("{length_hours} Hours" or "{length_hours}H") in at least 2 titles
- Primary keyword in the first 5 words of at least one title
- Be specific and evocative — describe the setting and mood  
- Under 70 characters each (YouTube truncates longer titles)
- No clickbait, no all-caps, no emoji

Return ONLY a JSON array with exactly 3 objects, each with "title" and "seo_score" (1-10):
[{{"title": "...", "seo_score": 8}}, ...]
""")
    try:
        titles_data = json.loads(titles_raw.strip())
        # Support both [{"title": ..., "seo_score": ...}] and ["title", ...]
        if isinstance(titles_data[0], dict):
            titles_data.sort(key=lambda x: x.get("seo_score", 0), reverse=True)
            titles = [t["title"] for t in titles_data]
        else:
            titles = titles_data
        selected_title = titles[0]
    except Exception:
        selected_title = f"{niche.title()} — {length_hours} Hours of {angle.title()}"
    log.append(f"[{ts()}] INFO  Selected title: {selected_title}")
    supabase.update_run_log(run_id, log[-1:], progress=25)

    # Step 2: Generate SEO-optimised description (CORE-EEAT from seo-content-writer skill)
    log.append(f"[{ts()}] INFO  Generating SEO description...")
    description = openai_tool.generate_text(f"""
Write a YouTube video description for: "{selected_title}"
Primary keywords: {', '.join(seo_keywords[:3])}

Requirements (follow CORE-EEAT SEO standards):
- 400-500 words total
- First 2 sentences (visible before "show more"): directly describe what the viewer will hear/experience
  and include the primary keyword naturally
- Section: "Perfect for..." — list: studying, deep focus, sleep, relaxation, work from home, anxiety relief
- Section: "What you'll hear:" — 3-4 bullet points describing the soundscape
- Section: "Video details:" — duration, audio type (CC0 ambient loops, royalty-free)
- Call to action: subscribe + like
- End with: "🎵 All audio is royalty-free CC0 — safe to use in streams and videos."
- Natural, engaging tone — not robotic
- Do NOT include chapter timestamps

Keyword integration rules:
- Primary keyword in first 100 words
- Secondary keywords naturally 2-3 times in body
- No keyword stuffing
""")
    supabase.update_run_log(run_id, [f"[{ts()}] INFO  Description written ({len(description)} chars)"], progress=45)

    # Step 3: Generate tags
    log.append(f"[{ts()}] INFO  Generating tags...")
    tags_raw = openai_tool.generate_text(f"""
Generate 15 YouTube tags for: "{selected_title}"
Niche: {niche}

Rules:
- Mix specific and broad tags
- Include duration-related tags (e.g. "3 hour study music")
- Include the niche keywords people actually search for
- No # prefix

Return ONLY a JSON array of 15 strings. No other text.
""")
    try:
        tags = json.loads(tags_raw.strip())
    except Exception:
        tags = [niche, f"{niche} {length_hours} hours", "ambient music", "study music", "sleep sounds"]
    supabase.update_run_log(run_id, [f"[{ts()}] INFO  Generated {len(tags)} tags"], progress=60)

    # Step 4: Generate thumbnail prompt and image
    log.append(f"[{ts()}] INFO  Generating thumbnail...")
    thumb_prompt = openai_tool.generate_text(f"""
Write an image generation prompt for a YouTube thumbnail for: "{selected_title}"

Requirements:
- Cinematic, atmospheric, moody lighting
- No text in the image
- Photorealistic or painterly — evocative of the setting
- 16:9 ratio composition
- Should make someone want to click when scrolling

Return ONLY the prompt text. No other text.
""")
    img_result = openai_tool.generate_image(thumb_prompt, size="1792x1024")
    thumb_id = str(_uuid.uuid4())[:8]
    thumb_local = f"/tmp/thumb_{thumb_id}.jpg"
    with open(thumb_local, "wb") as f:
        f.write(img_result["image_bytes"])
    thumbnail_url = storage.upload_file(thumb_local, "thumbnails", f"{thumb_id}.jpg")
    log.append(f"[{ts()}] INFO  Thumbnail generated and uploaded: {thumbnail_url[:60]}...")
    supabase.update_run_log(run_id, log[-1:], progress=85)

    # Step 5: Write to content_queue
    row = supabase.insert("content_queue", {
        "title": selected_title,
        "niche": niche,
        "angle": angle,
        "status": "awaiting_approval",
        "length_hours": length_hours,
        "description": description,
        "tags": tags,
        "thumbnail_url": thumbnail_url,
        "priority": input_data.get("priority", "high"),
        "pipeline_run_id": input_data.get("pipeline_run_id"),
        "brainstorm_run_id": input_data.get("brainstorm_run_id"),
    })
    content_id = row.get("id", "unknown")
    log.append(f"[{ts()}] INFO  Content brief saved — ID: {content_id}, status: awaiting_approval")
    supabase.update_run_log(run_id, log[-1:], progress=100)

    return {
        "summary": f"Created content brief: '{selected_title}' — awaiting approval",
        "log": log,
        "result": {"content_id": content_id, "title": selected_title},
        "progress": 100,
    }
