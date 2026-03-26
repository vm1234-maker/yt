# Autonomy Checklist
## What's done, what's left, and the exact steps to go fully hands-off

---

## Current State

The system is fully built. All agents, the pipeline, visuals, audio, and the dashboard are complete.
The only things preventing lights-out autonomous operation are listed below.

---

## ✅ Already Done

| Component | Detail |
|---|---|
| 6 agents | Research, Brainstorm, Content, Production, Upload, Analytics |
| Full pipeline | `backend/pipeline.py` — chains all agents sequentially |
| Multi-agent brainstorm | 4-turn discussion between Research + Strategy + Content before writing |
| 44 CC0 visual loops | 3–5 variants per niche in `backend/visuals/` |
| 36 CC0 audio loops | 3 variants per niche in `backend/audio/` |
| Audio + visual niche matching | Production Agent always pairs same-niche audio + visual randomly |
| Supabase schema | `agent_runs`, `content_queue`, `video_analytics`, `channel_metrics`, views |
| Supabase buckets | `videos` (5 GB limit) and `thumbnails` (10 MB limit), both public |
| Analytics auto-schedule | Celery beat runs Analytics Agent every day at **4 AM** |
| iMessage summary schedule | Celery beat sends morning report via iMessage every day at **8 AM** |
| Content approval gate | Pipeline pauses at `awaiting_approval` — NemoClaw auto-approves or pings you |
| Next.js dashboard | Live agent cards, analytics charts, content queue, pipeline trigger button |
| NemoClaw agent instructions | `nemoclaw/agent-instructions.md` — full decision rules loaded |
| NemoClaw tools | `read_analytics`, `trigger_agent`, `send_imessage`, `approve_content` |
| Docker backend | FastAPI + Celery worker + Celery beat — single `docker compose up -d` |

---

## 🔴 Blockers — Nothing Works Without These

### 1. Add OpenAI Credits

**Why it's needed**: The Content Agent (title, description, tags) and Production Agent (thumbnail via
`gpt-image-1`) both call OpenAI. Without credits the pipeline errors out after Research.

**Fix**: Go to [platform.openai.com/billing](https://platform.openai.com/billing) and add $20–50.
Your API key is already in `backend/.env` — no code changes needed.

**Cost estimate per video**: ~$0.10–0.30 (text) + ~$0.08 (one thumbnail image) = under $0.40/video.

---

### 2. Install NemoClaw on Your Mac

**Why it's needed**: NemoClaw is the always-on manager that reads analytics every morning and
triggers the pipeline automatically. Without it, nothing runs unless you click the dashboard button
yourself.

**Fix**: Follow `plans/NEMOCLAW-SETUP.md` — takes ~20 minutes.

Quick summary:
```bash
# Install OpenShell
npm install -g @nemoclaw/opensh

# Onboard (creates sandbox, loads your NVIDIA API key)
opensh onboard

# Apply the custom network policy
opensh policy apply nemoclaw/openclaw-sandbox.yaml

# Load agent instructions
opensh agent load nemoclaw/agent-instructions.md

# Copy tools into sandbox
opensh cp nemoclaw/tools/ /sandbox/tools/

# Start the agent (runs in background)
opensh agent start --name yt-manager
```

**NVIDIA API key** (free): Get one at [build.nvidia.com](https://build.nvidia.com) —
NemoClaw uses Nemotron models which are free tier. OpenAI credits are separate.

---

## 🟡 Important — Fix Before First Full Automated Run

### 3. Verify YouTube OAuth Token

**Why it matters**: The YouTube refresh token in `backend/.env` may have expired if unused for
6+ months, or if your Google Cloud OAuth app is still in "test mode" (tokens expire after 7 days
in test mode).

**How to verify**: Manually trigger the Upload Agent once from the dashboard with a test
`content_id` and watch the agent log. If it returns a 401 or `invalid_grant` error, the token
has expired.

**Fix if expired**:
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Your project → APIs & Services → OAuth consent screen → publish the app (moves out of test mode)
3. Re-run the OAuth flow to get a fresh refresh token
4. Update `YOUTUBE_REFRESH_TOKEN` in `backend/.env`

---

### 4. Auto-Start Docker on Mac Reboot

**Why it matters**: Everything runs inside Docker. If your Mac restarts, the backend goes offline
and no agents run until you manually bring it back up.

**Fix**: Create a Mac launchd agent that runs `docker compose up -d` on login.

Create `/Library/LaunchDaemons/com.nemoclaw.yt.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.nemoclaw.yt</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/docker</string>
    <string>compose</string>
    <string>-f</string>
    <string>/Users/vishnumadichetty/Desktop/yt/backend/docker-compose.yml</string>
    <string>up</string>
    <string>-d</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
```
Then: `sudo launchctl load /Library/LaunchDaemons/com.nemoclaw.yt.plist`

---

## The Daily Autonomous Loop (once everything above is done)

```
4:00 AM  → Analytics Agent runs automatically (Celery beat)
           Pulls YouTube views, watch time, RPM, CTR → writes to Supabase

8:00 AM  → NemoClaw reads fresh analytics
           Builds morning report
           Sends iMessage to you: top video, revenue, what's running today

8:01 AM  → NemoClaw decides what to produce
           Reads niche_performance view (Strategy Agent logic)
           Picks best niche → fires POST /api/run-pipeline

8:01 AM+ → Full pipeline runs (~10–30 min):
           Research → Brainstorm → Content → [auto-approve] → Production → Upload

~8:30 AM → NemoClaw sends iMessage:
           "✅ Uploaded: '8 Hours Dark Forest Ambiance for Deep Focus'
            scheduled for 7am tomorrow. This week: 3/5 uploads done."

You do nothing.
```

---

## Decisions NemoClaw Makes For You (no iMessage needed)

- Approve content that passes quality checks (RPM ≥ $8, not a dead niche, title includes duration)
- Trigger Research, Analytics, Strategy agents
- Skip a niche if retention has been <20% across 5 uploads

## Decisions That Ping You via iMessage (need your reply)

- Pivoting away from a proven niche
- Uploading more than 7 videos in a week
- Spending on a new API service
- Any agent that errors 3 times in a row

---

## Shortest Path to First Autonomous Upload

1. `platform.openai.com/billing` → add $20
2. Follow `plans/NEMOCLAW-SETUP.md` (~20 min)
3. `cd backend && docker compose up -d`
4. `cd .. && npm run dev`
5. Open dashboard → run Upload Agent once manually to verify YouTube OAuth
6. Go to sleep. Wake up to an iMessage.
