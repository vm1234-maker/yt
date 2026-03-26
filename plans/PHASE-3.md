# Phase 3 — Agent Implementations

**Goal**: Replace every placeholder `dispatch_agent` branch in `backend/tasks.py` with real API calls.
Build agents in dependency order: Research → Content → Production → Upload → Analytics → Strategy.

**Depends on**: Phase 2 complete (FastAPI + Celery running, Supabase wired)

---

## Dependency Order

```
Research  →  feeds niche data to  →  Strategy
Content   →  feeds briefs to      →  Production
Production →  feeds MP4 to        →  Upload
Upload    →  feeds video IDs to   →  Analytics
Analytics →  feeds perf data to   →  Strategy (closes the loop)
Strategy  →  triggers             →  Content (starts next cycle)
```

Build and test each agent before moving to the next.

---

## Agent 1 — Research Agent

### New files
- `backend/tools/serpapi.py`
- `backend/tools/youtube_search.py`
- `backend/agents/research.py`

### New credentials needed
Add to `backend/.env`:
```
SERPAPI_KEY=
YOUTUBE_API_KEY=
```

### `backend/tools/serpapi.py`

```python
import httpx
from config import settings

class SerpAPITool:
    BASE = "https://serpapi.com/search"

    def youtube_search(self, query: str) -> dict:
        r = httpx.get(self.BASE, params={
            "engine": "youtube",
            "search_query": query,
            "api_key": settings.SERPAPI_KEY
        }, timeout=30)
        r.raise_for_status()
        return r.json()

    def google_trends(self, keyword: str) -> dict:
        r = httpx.get(self.BASE, params={
            "engine": "google_trends",
            "q": keyword,
            "data_type": "TIMESERIES",
            "api_key": settings.SERPAPI_KEY
        }, timeout=30)
        r.raise_for_status()
        return r.json()
```

### `backend/tools/youtube_search.py`

```python
from googleapiclient.discovery import build
from config import settings

class YouTubeSearchTool:
    def __init__(self):
        self.yt = build('youtube', 'v3', developerKey=settings.YOUTUBE_API_KEY)

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        resp = self.yt.search().list(
            q=query, part='snippet,id', type='video',
            order='viewCount', maxResults=max_results
        ).execute()
        return resp.get('items', [])

    def video_stats(self, video_ids: list[str]) -> list[dict]:
        resp = self.yt.videos().list(
            part='statistics,contentDetails',
            id=','.join(video_ids)
        ).execute()
        return resp.get('items', [])
```

### `backend/agents/research.py`

```python
import datetime
from tools.serpapi import SerpAPITool
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
    serpapi = SerpAPITool()
    youtube = YouTubeSearchTool()
    supabase = SupabaseTool()
    log = []

    def ts():
        return datetime.datetime.utcnow().strftime('%H:%M:%S')

    niches_to_scan = input_data.get("niches", TARGET_NICHES)
    results = []

    for i, niche in enumerate(niches_to_scan):
        log.append(f"[{ts()}] INFO  Processing niche {i+1}/{len(niches_to_scan)}: {niche}")
        supabase.update_run_log(run_id, log[-1:], progress=int((i / len(niches_to_scan)) * 100))

        # Competition: count top-20 search results with >1M views
        try:
            yt_results = youtube.search(niche, max_results=20)
            video_ids = [r["id"].get("videoId") for r in yt_results if r["id"].get("videoId")]
            stats = youtube.video_stats(video_ids) if video_ids else []
            high_view_count = sum(1 for s in stats if int(s.get("statistics", {}).get("viewCount", 0)) > 1_000_000)
            competition = "high" if high_view_count >= 10 else "medium" if high_view_count >= 5 else "low"
            competition_score = {"high": 0.3, "medium": 0.6, "low": 1.0}[competition]
        except Exception as e:
            log.append(f"[{ts()}] WARN  YouTube search failed for '{niche}': {e}")
            competition = "unknown"
            competition_score = 0.5

        # Trend: simple up/down from Google Trends (last 30 days)
        try:
            trends = serpapi.google_trends(f"{niche} youtube")
            timeline = trends.get("interest_over_time", {}).get("timeline_data", [])
            if len(timeline) >= 4:
                recent = sum(int(t["values"][0].get("extracted_value", 0)) for t in timeline[-4:])
                older = sum(int(t["values"][0].get("extracted_value", 0)) for t in timeline[-8:-4])
                trend = "up" if recent > older else "down" if recent < older else "flat"
                trend_score = {"up": 1.0, "flat": 0.5, "down": 0.2}[trend]
            else:
                trend = "unknown"
                trend_score = 0.5
        except Exception as e:
            log.append(f"[{ts()}] WARN  Trends fetch failed for '{niche}': {e}")
            trend = "unknown"
            trend_score = 0.5

        rpm = RPM_TABLE.get(niche, 9.0)
        rpm_score = min((rpm - 7.0) / 6.0, 1.0)  # normalize $7-$13 range to 0-1
        score = round((rpm_score * 0.4 + competition_score * 0.4 + trend_score * 0.2) * 100)

        results.append({
            "name": niche,
            "rpm_estimate": rpm,
            "competition": competition,
            "trend": trend,
            "score": score,
        })
        log.append(f"[{ts()}] INFO  {niche}: RPM ${rpm}, competition={competition}, trend={trend}, score={score}")

    results.sort(key=lambda x: x["score"], reverse=True)
    log.append(f"[{ts()}] INFO  Research complete. Top niche: {results[0]['name']} (score {results[0]['score']})")

    return {
        "summary": f"Scanned {len(results)} niches. Top: {results[0]['name']} (RPM ${results[0]['rpm_estimate']}, score {results[0]['score']})",
        "log": log,
        "result": {"niches": results},
        "progress": 100,
    }
```

### Update `backend/tasks.py` dispatch_agent

```python
# Replace the research branch:
if agent_name == "research":
    from agents.research import run_research_agent
    return run_research_agent(run_id, input_data)
```

---

## Agent 2 — Content Agent

### New files
- `backend/tools/claude_tool.py`
- `backend/tools/dalle_tool.py`
- `backend/agents/content.py`

### New credentials needed
```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

### `backend/tools/claude_tool.py`

```python
import anthropic
from config import settings

class ClaudeTool:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        msg = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
```

### `backend/tools/dalle_tool.py`

```python
from openai import OpenAI
from config import settings

class DallETool:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def generate(self, prompt: str) -> str:
        """Returns URL to generated 1792x1024 image (YouTube thumbnail ratio)."""
        r = self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="hd",
            n=1,
        )
        return r.data[0].url
```

### `backend/agents/content.py`

```python
import datetime
import json
from tools.claude_tool import ClaudeTool
from tools.dalle_tool import DallETool
from tools.supabase_tool import SupabaseTool

TITLE_PATTERNS = [
    '"X Hours of Y" (e.g. "3 Hours of Deep Forest Rain")',
    '"Cozy [Setting] Ambiance" (e.g. "Cozy Coffee Shop Ambiance")',
    '"[Setting] Sounds for Sleep/Study/Focus"',
    '"Dark/Deep [Setting] for Focus/Work"',
]


def run_content_agent(run_id: str, input_data: dict) -> dict:
    niche = input_data.get("niche", "rain sounds")
    angle = input_data.get("angle", "study and focus")
    length_hours = input_data.get("length_hours", 3)

    claude = ClaudeTool()
    dalle = DallETool()
    supabase = SupabaseTool()
    log = []

    def ts():
        return datetime.datetime.utcnow().strftime('%H:%M:%S')

    # Step 1: Generate title variants
    log.append(f"[{ts()}] INFO  Generating title variants for: {niche} / {angle}")
    supabase.update_run_log(run_id, log[-1:], progress=10)

    titles_raw = claude.generate(f"""
Generate 3 YouTube video title variants for an ambient/soundscape video.
Niche: {niche}
Angle: {angle}
Duration: {length_hours} hours

Use these patterns for inspiration: {', '.join(TITLE_PATTERNS)}

Rules:
- Include the duration ("{length_hours} Hours" or "{length_hours}HR") in at least 2 titles
- Be specific and evocative — describe the setting and mood
- No clickbait, no all-caps

Return ONLY a JSON array of 3 strings. No other text.
Example: ["Title 1", "Title 2", "Title 3"]
""")
    try:
        titles = json.loads(titles_raw.strip())
        selected_title = titles[0]
    except Exception:
        selected_title = f"{niche.title()} — {length_hours} Hours of {angle.title()}"
    log.append(f"[{ts()}] INFO  Selected title: {selected_title}")
    supabase.update_run_log(run_id, log[-1:], progress=25)

    # Step 2: Generate description
    log.append(f"[{ts()}] INFO  Generating description...")
    description = claude.generate(f"""
Write a YouTube video description for: "{selected_title}"

Requirements:
- 400-500 words
- First 2 sentences describe exactly what the viewer will hear/experience
- Mention it's perfect for: studying, focus, sleep, relaxation, work from home
- Include a call to action (subscribe, like)
- End with: "All audio generated with Suno AI — 100% original, royalty-free."
- Natural, engaging tone — not robotic

Do not include timestamps or chapter markers.
""")
    supabase.update_run_log(run_id, [f"[{ts()}] INFO  Description written ({len(description)} chars)"], progress=45)

    # Step 3: Generate tags
    log.append(f"[{ts()}] INFO  Generating tags...")
    tags_raw = claude.generate(f"""
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

    # Step 4: Generate thumbnail prompt
    log.append(f"[{ts()}] INFO  Generating thumbnail...")
    thumb_prompt = claude.generate(f"""
Write a DALL-E 3 image generation prompt for a YouTube thumbnail for: "{selected_title}"

Requirements:
- Cinematic, atmospheric, moody lighting
- No text in the image
- Photorealistic or painterly — evocative of the setting
- 16:9 ratio composition
- Should make someone want to click when scrolling

Return ONLY the prompt text. No other text.
""")
    thumbnail_url = dalle.generate(thumb_prompt)
    log.append(f"[{ts()}] INFO  Thumbnail generated: {thumbnail_url[:60]}...")
    supabase.update_run_log(run_id, log[-1:], progress=85)

    # Step 5: Write to content_queue
    row = supabase.insert("content_queue", {
        "title": selected_title,
        "niche": niche,
        "status": "awaiting_approval",
        "length_hours": length_hours,
        "description": description,
        "tags": tags,
        "thumbnail_url": thumbnail_url,
        "priority": input_data.get("priority", "high"),
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
```

---

## Agent 3 — Production Agent

### New files
- `backend/tools/suno.py`
- `backend/tools/ffmpeg_tool.py`
- `backend/tools/replicate_tool.py`
- `backend/tools/supabase_storage.py`
- `backend/agents/production.py`

### New credentials needed
```
SUNO_API_KEY=
REPLICATE_API_TOKEN=
```

### `backend/tools/suno.py`

```python
import httpx
import time
from config import settings

class SunoTool:
    # Suno API wrapper — using apibox.erweima.ai as the official Suno API endpoint
    BASE = "https://apibox.erweima.ai/api/v1"

    def generate(self, prompt: str, duration_seconds: int) -> str:
        """Generate audio and return URL. Polls until complete."""
        headers = {"Authorization": f"Bearer {settings.SUNO_API_KEY}", "Content-Type": "application/json"}

        r = httpx.post(f"{self.BASE}/generate", headers=headers, json={
            "prompt": prompt,
            "duration": min(duration_seconds, 300),  # Suno max is 5 min; we loop in FFmpeg
            "make_instrumental": True,
        }, timeout=60)
        r.raise_for_status()
        task_id = r.json()["data"]["task_id"]

        # Poll for completion (max 30 minutes)
        deadline = time.time() + 1800
        while time.time() < deadline:
            status_r = httpx.get(f"{self.BASE}/task/{task_id}", headers=headers, timeout=30)
            status_r.raise_for_status()
            data = status_r.json()["data"]
            if data["status"] == "complete":
                return data["audio_url"]
            if data["status"] == "failed":
                raise RuntimeError(f"Suno generation failed: {data.get('error')}")
            time.sleep(15)

        raise TimeoutError("Suno audio generation timed out after 30 minutes")
```

### `backend/tools/ffmpeg_tool.py`

```python
import subprocess
import os
from pathlib import Path

SANDBOX = Path("/sandbox/output")

class FFmpegTool:
    def render(self, audio_path: str, visual_path: str, output_name: str, duration_s: int) -> str:
        """Loop visual to match audio duration, combine into MP4."""
        SANDBOX.mkdir(parents=True, exist_ok=True)
        out = SANDBOX / f"{output_name}.mp4"

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", visual_path,
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "slow", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration_s),
            "-movflags", "+faststart",
            "-shortest",
            str(out),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)  # 2hr timeout
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr[-1000:]}")

        return str(out)

    def download(self, url: str, dest: str) -> str:
        """Download a file from URL to dest path."""
        import httpx
        SANDBOX.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", url, timeout=300, follow_redirects=True) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)
        return dest
```

### `backend/tools/replicate_tool.py`

```python
import replicate
import time
from config import settings

# Map niche to Replicate model + prompt
VISUAL_STYLES = {
    "rain sounds": "dark rainy forest, cinematic, looping, 4K, moody atmosphere",
    "lo-fi study music": "cozy anime room, warm lighting, rain on window, looping",
    "dark forest ambiance": "dark forest at night, fog, moonlight through trees, looping",
    "coffee shop ambiance": "cozy coffee shop interior, warm light, people in background, looping",
    "fireplace crackle": "close up of fireplace flames, cozy, warm light, looping",
    "thunderstorm sounds": "dramatic storm clouds over forest, lightning in distance, looping",
    "binaural beats": "abstract flowing waves, deep blue and purple, mesmerizing, looping",
    "sleep sounds anxiety": "calm ocean waves at night, moonlight on water, looping",
    "nature ASMR": "peaceful forest clearing, sunlight through leaves, looping",
    "white noise": "abstract soft gradient, slowly shifting colors, minimal, looping",
    "ocean waves sleep": "ocean waves on beach at night, moonlit, looping",
    "forest birds morning": "forest at sunrise, golden light, birds in trees, looping",
}

class ReplicateTool:
    def generate_visual(self, niche: str) -> str:
        """Generate a looping video visual for the given niche. Returns URL."""
        import os
        os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN
        prompt = VISUAL_STYLES.get(niche, f"ambient {niche} scene, cinematic, looping, 4K")

        # Use stable-video-diffusion or similar model
        output = replicate.run(
            "stability-ai/stable-video-diffusion:3f0457e4619daac51203dedb472816fd4af51f3149fa7a9e0b5ffcf1b8172438",
            input={"input_image": generate_base_image(prompt), "video_length": "25_frames_with_svd_xt"}
        )
        return output[0] if isinstance(output, list) else output

def generate_base_image(prompt: str) -> str:
    """Generate base image for video using SDXL."""
    output = replicate.run(
        "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
        input={"prompt": prompt, "width": 1920, "height": 1080}
    )
    return output[0]
```

### `backend/tools/supabase_storage.py`

```python
import httpx
from pathlib import Path
from supabase import create_client
from config import settings

class SupabaseStorageTool:
    def __init__(self):
        self.db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    def upload_file(self, local_path: str, bucket: str, storage_path: str) -> str:
        """Upload file to Supabase Storage, return public URL."""
        with open(local_path, "rb") as f:
            data = f.read()

        mime = "video/mp4" if local_path.endswith(".mp4") else "image/jpeg"
        self.db.storage.from_(bucket).upload(
            path=storage_path,
            file=data,
            file_options={"content-type": mime, "upsert": "true"}
        )
        return self.db.storage.from_(bucket).get_public_url(storage_path)
```

### `backend/agents/production.py`

```python
import datetime
import uuid
from tools.suno import SunoTool
from tools.ffmpeg_tool import FFmpegTool
from tools.replicate_tool import ReplicateTool
from tools.supabase_tool import SupabaseTool
from tools.supabase_storage import SupabaseStorageTool
from pathlib import Path

SANDBOX = Path("/sandbox/output")

def run_production_agent(run_id: str, input_data: dict) -> dict:
    content_id = input_data.get("content_id")
    if not content_id:
        raise ValueError("production agent requires content_id in input")

    suno = SunoTool()
    ffmpeg = FFmpegTool()
    replicate = ReplicateTool()
    supabase = SupabaseTool()
    storage = SupabaseStorageTool()
    log = []

    def ts():
        return datetime.datetime.utcnow().strftime('%H:%M:%S')

    # Fetch content brief
    rows = supabase.select("content_queue", {"id": content_id}, limit=1)
    if not rows:
        raise ValueError(f"content_id {content_id} not found in content_queue")
    content = rows[0]
    niche = content.get("niche", "rain sounds")
    length_hours = content.get("length_hours", 3)
    duration_s = int(length_hours * 3600)
    job_id = str(uuid.uuid4())[:8]

    supabase.update("content_queue", {"status": "in_production"}, {"id": content_id})
    log.append(f"[{ts()}] INFO  Starting production for: {content['title']}")
    log.append(f"[{ts()}] INFO  Duration: {length_hours}h ({duration_s}s), Niche: {niche}")
    supabase.update_run_log(run_id, log, progress=5)

    # Step 1: Generate audio via Suno (generate 5min loop, FFmpeg will extend)
    log.append(f"[{ts()}] INFO  Requesting audio from Suno API (5 min loop for {niche})...")
    supabase.update_run_log(run_id, log[-1:], progress=10)
    audio_url = suno.generate(prompt=f"{niche} ambient audio, peaceful, high quality", duration_seconds=300)
    audio_local = str(SANDBOX / f"{job_id}_audio.mp3")
    ffmpeg.download(audio_url, audio_local)
    log.append(f"[{ts()}] INFO  Audio downloaded: {audio_local}")
    supabase.update_run_log(run_id, log[-1:], progress=30)

    # Step 2: Generate visual via Replicate
    log.append(f"[{ts()}] INFO  Generating looping visual for niche: {niche}...")
    supabase.update_run_log(run_id, log[-1:], progress=35)
    visual_url = replicate.generate_visual(niche)
    visual_local = str(SANDBOX / f"{job_id}_visual.mp4")
    ffmpeg.download(visual_url, visual_local)
    log.append(f"[{ts()}] INFO  Visual downloaded: {visual_local}")
    supabase.update_run_log(run_id, log[-1:], progress=50)

    # Step 3: Render final video
    log.append(f"[{ts()}] INFO  FFmpeg render starting — {duration_s}s output...")
    supabase.update_run_log(run_id, log[-1:], progress=55)
    output_path = ffmpeg.render(audio_local, visual_local, f"{job_id}_final", duration_s)
    log.append(f"[{ts()}] INFO  Render complete: {output_path}")
    supabase.update_run_log(run_id, log[-1:], progress=85)

    # Step 4: Upload to Supabase Storage
    log.append(f"[{ts()}] INFO  Uploading to Supabase Storage...")
    video_url = storage.upload_file(output_path, "videos", f"{job_id}.mp4")
    log.append(f"[{ts()}] INFO  Upload complete: {video_url[:60]}...")
    supabase.update_run_log(run_id, log[-1:], progress=95)

    # Step 5: Update content_queue
    supabase.update("content_queue", {"video_url": video_url, "status": "approved"}, {"id": content_id})
    log.append(f"[{ts()}] INFO  content_queue updated — status: approved, video_url set")
    supabase.update_run_log(run_id, log[-1:], progress=100)

    return {
        "summary": f"Production complete for '{content['title']}' — MP4 ready for upload",
        "log": log,
        "result": {"content_id": content_id, "video_url": video_url},
        "progress": 100,
    }
```

---

## Agent 4 — Upload Agent

### New files
- `backend/tools/youtube_upload.py`
- `backend/tools/youtube_auth.py` (one-time OAuth2 setup script)
- `backend/agents/upload.py`

### One-time setup (run locally once)
```bash
cd backend
python tools/youtube_auth.py
# Opens browser → authorize → prints YOUTUBE_REFRESH_TOKEN to copy into .env
```

### `backend/tools/youtube_auth.py`

```python
"""
Run once to generate YOUTUBE_REFRESH_TOKEN.
Usage: python tools/youtube_auth.py
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": input("Enter YOUTUBE_CLIENT_ID: ").strip(),
            "client_secret": input("Enter YOUTUBE_CLIENT_SECRET: ").strip(),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
        }
    },
    scopes=SCOPES,
)
creds = flow.run_local_server(port=0)
print(f"\nYOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
```

### `backend/tools/youtube_upload.py`

```python
import os
import httpx
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import settings

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]

def get_youtube_client():
    creds = Credentials(
        token=None,
        refresh_token=settings.YOUTUBE_REFRESH_TOKEN,
        client_id=settings.YOUTUBE_CLIENT_ID,
        client_secret=settings.YOUTUBE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build('youtube', 'v3', credentials=creds)

class YouTubeUploadTool:
    def upload(self, video_path: str, title: str, description: str,
               tags: list[str], scheduled_for: str | None = None) -> str:
        """Upload video, return YouTube video ID."""
        yt = get_youtube_client()

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags[:15],  # YouTube limit
                "categoryId": "10",  # Music
            },
            "status": {
                "privacyStatus": "private" if scheduled_for else "public",
                "publishAt": scheduled_for,
                "selfDeclaredMadeForKids": False,
            },
        }

        # Download from Supabase Storage to local if it's a URL
        local_path = video_path
        if video_path.startswith("http"):
            local_path = f"/tmp/upload_{title[:20].replace(' ', '_')}.mp4"
            with httpx.stream("GET", video_path, timeout=600, follow_redirects=True) as r:
                r.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in r.iter_bytes(1024 * 1024):
                        f.write(chunk)

        media = MediaFileUpload(local_path, chunksize=50 * 1024 * 1024,
                                resumable=True, mimetype="video/mp4")
        request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            _, response = request.next_chunk()

        return response["id"]

    def set_thumbnail(self, video_id: str, thumbnail_url: str) -> None:
        yt = get_youtube_client()
        img_data = httpx.get(thumbnail_url, timeout=30).content
        tmp = f"/tmp/thumb_{video_id}.jpg"
        with open(tmp, "wb") as f:
            f.write(img_data)
        yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(tmp)).execute()
```

### `backend/agents/upload.py`

```python
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
```

---

## Agent 5 — Analytics Agent

### New files
- `backend/tools/youtube_analytics.py`
- `backend/agents/analytics.py`

### `backend/tools/youtube_analytics.py`

```python
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config import settings
import datetime

SCOPES = ["https://www.googleapis.com/auth/yt-analytics.readonly"]

def get_analytics_client():
    creds = Credentials(
        token=None,
        refresh_token=settings.YOUTUBE_REFRESH_TOKEN,
        client_id=settings.YOUTUBE_CLIENT_ID,
        client_secret=settings.YOUTUBE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build('youtubeAnalytics', 'v2', credentials=creds)

class YouTubeAnalyticsTool:
    def get_video_metrics(self, video_id: str) -> dict:
        yt = get_analytics_client()
        end = datetime.date.today().isoformat()
        start = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

        r = yt.reports().query(
            ids="channel==MINE",
            startDate=start,
            endDate=end,
            metrics="views,estimatedMinutesWatched,estimatedRevenue,annotationClickThroughRate,averageViewDuration",
            dimensions="video",
            filters=f"video=={video_id}",
        ).execute()

        rows = r.get("rows", [])
        if not rows:
            return {}
        row = rows[0]
        return {
            "views": int(row[1]),
            "watch_time_minutes": int(row[2]),
            "estimated_revenue": float(row[3]),
            "ctr": float(row[4]),
            "avg_view_duration_seconds": int(row[5]),
        }

    def get_channel_rollup(self) -> dict:
        yt = get_analytics_client()
        end = datetime.date.today().isoformat()
        start = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

        r = yt.reports().query(
            ids="channel==MINE",
            startDate=start,
            endDate=end,
            metrics="views,estimatedMinutesWatched,estimatedRevenue,subscribersGained,annotationClickThroughRate",
        ).execute()

        row = r.get("rows", [[0, 0, 0, 0, 0]])[0]
        return {
            "total_views": int(row[0]),
            "total_watch_hours": round(int(row[1]) / 60, 1),
            "estimated_revenue": float(row[2]),
            "subscribers_gained": int(row[3]),
            "avg_ctr": float(row[4]),
            "period_start": start,
            "period_end": end,
        }
```

### `backend/agents/analytics.py`

```python
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
                    "views": metrics["views"],
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
```

---

## Agent 6 — Strategy Agent

### New files
- `backend/agents/strategy.py`

### `backend/agents/strategy.py`

```python
import datetime
import json
from tools.claude_tool import ClaudeTool
from tools.supabase_tool import SupabaseTool

PROVEN_THRESHOLD_RETENTION_30 = 0.40   # 40% retention at 30min = niche is proven
DEAD_THRESHOLD_RETENTION_10 = 0.20     # <20% retention at 10min after 5 uploads = kill
MIN_UPLOADS_TO_PROVE = 3
MIN_UPLOADS_TO_KILL = 5

def run_strategy_agent(run_id: str, input_data: dict) -> dict:
    claude = ClaudeTool()
    supabase = SupabaseTool()
    log = []

    def ts():
        return datetime.datetime.utcnow().strftime('%H:%M:%S')

    log.append(f"[{ts()}] INFO  Strategy Agent starting ROI analysis...")
    supabase.update_run_log(run_id, log, progress=5)

    # Load data
    analytics = supabase.select("video_analytics", {}, limit=500)
    channel = supabase.select("channel_metrics", {}, limit=1)
    queue = supabase.select("content_queue", {}, limit=200)

    # Load latest research report
    research_runs = supabase.select("agent_runs", {"agent_name": "research", "status": "success"}, limit=1)
    research_data = research_runs[0].get("full_output", {}).get("result", {}) if research_runs else {}

    log.append(f"[{ts()}] INFO  Loaded {len(analytics)} video analytics, {len(queue)} queue items")
    supabase.update_run_log(run_id, log[-1:], progress=15)

    # Group videos by niche
    niche_map: dict[str, list] = {}
    for v in analytics:
        vid = next((q for q in queue if q.get("youtube_video_id") == v.get("youtube_video_id")), {})
        niche = vid.get("niche", "unknown")
        niche_map.setdefault(niche, []).append({**v, "length_hours": vid.get("length_hours", 3)})

    # ROI decisions
    plan = {"exploit": [], "test": [], "kill": [], "niche_decisions": {}}
    for niche, videos in niche_map.items():
        count = len(videos)
        avg_retention_30 = sum(
            v["avg_view_duration_seconds"] / (v["length_hours"] * 3600)
            for v in videos if v.get("avg_view_duration_seconds") and v.get("length_hours")
        ) / max(count, 1)
        avg_retention_10 = sum(
            min(v["avg_view_duration_seconds"] / 600, 1.0) for v in videos if v.get("avg_view_duration_seconds")
        ) / max(count, 1)

        if avg_retention_30 > PROVEN_THRESHOLD_RETENTION_30 and count >= MIN_UPLOADS_TO_PROVE:
            decision = "exploit"
        elif avg_retention_10 < DEAD_THRESHOLD_RETENTION_10 and count >= MIN_UPLOADS_TO_KILL:
            decision = "kill"
        else:
            decision = "test"

        plan[decision].append(niche)
        plan["niche_decisions"][niche] = {
            "decision": decision, "uploads": count,
            "avg_retention_30": round(avg_retention_30, 3),
            "avg_retention_10": round(avg_retention_10, 3),
        }
        log.append(f"[{ts()}] INFO  {niche}: {decision} (uploads={count}, ret30={avg_retention_30:.0%})")

    supabase.update_run_log(run_id, log[-2:], progress=50)

    # Ask Claude to pick the next best niche + angle
    research_niches = research_data.get("niches", [])[:5]
    top_pick_raw = claude.generate(f"""
You are the content strategy brain for a YouTube ambient/soundscape channel.

Current performance data:
- Exploit niches (high retention, proven): {plan['exploit']}
- Test niches (collecting data): {plan['test']}
- Kill niches (low retention, drop): {plan['kill']}

Latest research top niches: {json.dumps(research_niches, indent=2)}

Pick the single best niche and angle for the NEXT video to produce.
Prioritize: exploit niches first, then high-score research niches.
Avoid kill niches entirely.

Business rules:
- RPM floor: avoid niches estimated below $8/RPM
- Video length: 3h standard, 8h for sleep content, 1h for focus content
- Content must be unique — no repeating the same niche angle twice in a row

Return ONLY a JSON object:
{{
  "niche": "exact niche name",
  "angle": "specific angle/mood description",
  "length_hours": 3,
  "reasoning": "one sentence explanation"
}}
""")

    try:
        top_pick = json.loads(top_pick_raw.strip())
    except Exception:
        top_pick = {"niche": plan["exploit"][0] if plan["exploit"] else "rain sounds",
                    "angle": "study and focus", "length_hours": 3, "reasoning": "fallback"}

    log.append(f"[{ts()}] INFO  Next video: {top_pick['niche']} — {top_pick['angle']} ({top_pick['length_hours']}h)")
    log.append(f"[{ts()}] INFO  Reasoning: {top_pick.get('reasoning', '')}")
    supabase.update_run_log(run_id, log[-2:], progress=80)

    # Trigger Content Agent for next video
    log.append(f"[{ts()}] INFO  Triggering Content Agent...")
    import httpx, os
    app_url = os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
    try:
        httpx.post(f"{app_url}/api/run-agent", json={
            "agent": "content",
            "input": {
                "niche": top_pick["niche"],
                "angle": top_pick["angle"],
                "length_hours": top_pick["length_hours"],
            }
        }, timeout=15)
        log.append(f"[{ts()}] INFO  Content Agent triggered successfully")
    except Exception as e:
        log.append(f"[{ts()}] WARN  Failed to trigger Content Agent: {e}")

    supabase.update_run_log(run_id, log[-1:], progress=100)

    return {
        "summary": f"Strategy: exploit={plan['exploit']}, kill={plan['kill']}. Next: {top_pick['niche']} ({top_pick['length_hours']}h)",
        "log": log,
        "result": {"plan": plan, "top_pick": top_pick},
        "progress": 100,
    }
```

---

## Update `backend/tasks.py` dispatch_agent (final version)

```python
def dispatch_agent(agent_name: str, input_data: dict, run_id: str = None) -> dict:
    if agent_name == "research":
        from agents.research import run_research_agent
        return run_research_agent(run_id, input_data)
    elif agent_name == "content":
        from agents.content import run_content_agent
        return run_content_agent(run_id, input_data)
    elif agent_name == "production":
        from agents.production import run_production_agent
        return run_production_agent(run_id, input_data)
    elif agent_name == "upload":
        from agents.upload import run_upload_agent
        return run_upload_agent(run_id, input_data)
    elif agent_name == "analytics":
        from agents.analytics import run_analytics_agent
        return run_analytics_agent(run_id, input_data)
    elif agent_name == "strategy":
        from agents.strategy import run_strategy_agent
        return run_strategy_agent(run_id, input_data)
    else:
        raise ValueError(f"Unknown agent: {agent_name}")
```
