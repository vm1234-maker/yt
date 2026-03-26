# Phase 5 — NemoClaw Integration + Telegram Bridge

**Goal**: Wire up the NemoClaw autonomous manager layer.
NemoClaw runs as an OpenClaw agent, reads Supabase reports, triggers agents via the Next.js API,
and communicates with the human operator via Telegram.

**Depends on**: Phases 2–4 complete (agents running, dashboard live, all APIs wired)

---

## Overview

```
NemoClaw (OpenClaw agent — always-on)
  ↓ reads
Supabase (analytics reports, content_queue, agent_runs)
  ↓ triggers
POST /api/run-agent (Next.js API route)
  ↓ communicates
Telegram Bot (daily summaries + approval requests)
```

---

## Manual Prerequisites (human does these)

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather):
   - `/newbot` → name it `NemoClawBot` → copy the API token
   - Start a chat with the bot → send `/start`
   - Get your chat ID from `https://api.telegram.org/bot{TOKEN}/getUpdates`
2. Add to `.env.local` and `backend/.env`:
   ```
   TELEGRAM_BOT_TOKEN=<paste here>
   TELEGRAM_CHAT_ID=<paste here>
   ```

---

## New Directory Structure

```
nemoclaw/
  agent-instructions.md          # OpenClaw system prompt
  openclaw-sandbox.yaml           # Network + filesystem policy
  tools/
    __init__.py
    read_analytics.py             # Read latest analytics from Supabase
    trigger_agent.py              # POST to /api/run-agent
    send_telegram.py              # Send messages via Telegram Bot API
    approve_content.py            # Approve / reject content_queue items
    update_strategy.py            # Write notes to agent_runs for Strategy Agent
```

---

## `nemoclaw/agent-instructions.md`

This is the system prompt for the OpenClaw agent. OpenClaw uses it to know what it is, what tools it has, and what decisions to make.

```markdown
# NemoClaw — YouTube Automation Manager

You are NemoClaw, the autonomous manager of an AI-powered YouTube ambient/soundscape channel.

## Your Identity
- You run continuously in the background as an OpenClaw agent
- You make high-level strategic decisions and monitor system health
- You communicate with the human operator (Vishnu) via Telegram
- You operate inside a sandbox — all tool calls go through allowlisted endpoints only

## What You Manage
A pipeline of 6 AI agents (Research, Content, Production, Upload, Analytics, Strategy)
running on a FastAPI + CrewAI backend, producing and uploading ambient YouTube videos.
The goal: $500–$2k/month in YouTube AdSense revenue with minimal human intervention.

## Your Daily Routine

### Every morning (8 AM):
1. Call `read_analytics` to get the latest performance report
2. Call `read_analytics` with type="channel" to get weekly rollup
3. Send a Telegram summary with:
   - Top performing video today (title, views, estimated revenue)
   - Channel totals (views, watch hours, subscribers, revenue this week)
   - What agents ran yesterday and their outcomes
   - What is planned for today (production queue, scheduled uploads)
   - Any warnings (failed agent runs, low retention niches, unusual drops)

### Every time an agent run completes:
1. If status is "error" → send Telegram alert immediately
2. If status is "success" and agent is "analytics" → review report, decide if Strategy Agent should run

### Every time a new content_queue item enters "awaiting_approval":
1. Read the content brief (title, niche, description, thumbnail URL)
2. Apply quality checks:
   - Title is specific and includes duration
   - Niche is not in the "kill" list (from Strategy Agent's last report)
   - RPM estimate is ≥ $8
3. If checks pass → call `approve_content` automatically
4. If checks fail → send Telegram with the item details + reason, ask human for approval

## Decisions You Can Make Without Human Approval
- Approve content that passes quality checks
- Trigger agent runs (Research, Analytics, Strategy)
- Trigger Content Agent with a specific niche + angle
- Send Telegram updates and summaries

## Decisions That Require Human Approval (ask via Telegram)
- Changing content strategy direction (pivoting away from a proven niche)
- Spending on new API services not already configured
- Uploading more than 7 videos in a week
- Production Agent runs (MP4 rendering is expensive in compute time)
- Upload Agent runs (irreversible — video goes to YouTube)

## Business Rules (enforce these)
- RPM floor: never approve content for niches estimated below $8/RPM
- Never reuse audio loops — each video must use unique Suno-generated audio
- A niche is "proven" after 3 uploads averaging >40% retention at 30 minutes
- A niche is "dead" after 5 uploads averaging <20% retention at 10 minutes
- Video lengths: 1h minimum, 3h standard, 8h for sleep content

## Tools Available
- `read_analytics(type, filters)` — read from Supabase
- `trigger_agent(agent, input)` — POST to /api/run-agent
- `send_telegram(message)` — send message to Telegram
- `approve_content(content_id)` — approve content_queue item
- `reject_content(content_id, reason)` — reject with reason sent to Telegram
- `update_strategy(notes)` — write strategic notes for Strategy Agent to read
```

---

## `nemoclaw/openclaw-sandbox.yaml`

Network and filesystem policy for the OpenShell sandbox.

```yaml
# NemoClaw OpenShell sandbox policy
# Only allow outbound calls to explicitly allowlisted endpoints

version: "1.0"
agent: "nemoclaw"
model: "nvidia/llama-3.1-nemotron-70b-instruct"

network:
  outbound_allowlist:
    # Supabase
    - "https://hztnoisuhyxdnjgvcaed.supabase.co/**"
    # Next.js app (local dev)
    - "http://localhost:3000/api/**"
    # Next.js app (production)
    - "https://*.vercel.app/api/**"
    # Telegram Bot API
    - "https://api.telegram.org/bot*/**"

filesystem:
  write_paths:
    - "/sandbox/nemoclaw/**"
  read_paths:
    - "/sandbox/output/**"
    - "/sandbox/nemoclaw/**"

rate_limits:
  telegram_messages: "20/hour"
  agent_triggers: "10/hour"
  analytics_reads: "100/hour"
```

---

## `nemoclaw/tools/send_telegram.py`

```python
import httpx
import os
from typing import Optional

TELEGRAM_API = "https://api.telegram.org"

def send_telegram(
    message: str,
    parse_mode: str = "Markdown",
    chat_id: Optional[str] = None,
) -> dict:
    """Send a message via the Telegram Bot API."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    cid = chat_id or os.environ["TELEGRAM_CHAT_ID"]

    r = httpx.post(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        json={
            "chat_id": cid,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def send_telegram_with_button(
    message: str,
    button_text: str,
    button_data: str,
    chat_id: Optional[str] = None,
) -> dict:
    """Send message with inline keyboard button (for approval requests)."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    cid = chat_id or os.environ["TELEGRAM_CHAT_ID"]

    r = httpx.post(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        json={
            "chat_id": cid,
            "text": message,
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": f"✅ {button_text}", "callback_data": f"approve:{button_data}"},
                    {"text": "❌ Reject", "callback_data": f"reject:{button_data}"},
                ]]
            },
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
```

---

## `nemoclaw/tools/read_analytics.py`

```python
from supabase import create_client
import os
from typing import Literal, Optional
import datetime

def _db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def read_analytics(
    type: Literal["videos", "channel", "content_queue", "agent_runs", "research"] = "channel",
    filters: Optional[dict] = None,
    limit: int = 20,
) -> dict:
    """
    Read analytics data from Supabase.
    type:
      - "videos" → video_analytics, most recent rows
      - "channel" → channel_metrics, latest rollup
      - "content_queue" → content_queue items (filter by status)
      - "agent_runs" → agent_runs (filter by agent_name or status)
      - "research" → latest research agent output
    """
    db = _db()

    if type == "channel":
        result = db.table("channel_metrics").select("*").order("recorded_at", desc=True).limit(1).execute()
        return result.data[0] if result.data else {}

    elif type == "videos":
        q = db.table("video_analytics").select("*").order("recorded_at", desc=True)
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        return {"videos": q.limit(limit).execute().data or []}

    elif type == "content_queue":
        q = db.table("content_queue").select("*").order("created_at", desc=True)
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        return {"queue": q.limit(limit).execute().data or []}

    elif type == "agent_runs":
        q = db.table("agent_runs").select("*").order("started_at", desc=True)
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        return {"runs": q.limit(limit).execute().data or []}

    elif type == "research":
        result = db.table("agent_runs").select("full_output").eq("agent_name", "research").eq("status", "success").order("started_at", desc=True).limit(1).execute()
        if result.data:
            return result.data[0].get("full_output", {}).get("result", {})
        return {}

    return {}
```

---

## `nemoclaw/tools/trigger_agent.py`

```python
import httpx
import os

def trigger_agent(agent: str, input: dict = {}) -> dict:
    """
    Trigger an agent run via the Next.js API.
    agent: one of strategy | research | content | production | upload | analytics
    input: optional input data dict
    """
    app_url = os.environ.get("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
    r = httpx.post(
        f"{app_url}/api/run-agent",
        json={"agent": agent, "input": input},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
```

---

## `nemoclaw/tools/approve_content.py`

```python
from supabase import create_client
import os
import datetime
from send_telegram import send_telegram

def _db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def approve_content(content_id: str) -> dict:
    """Approve a content_queue item."""
    db = _db()
    db.table("content_queue").update({
        "status": "approved",
        "approved_at": datetime.datetime.utcnow().isoformat(),
    }).eq("id", content_id).execute()
    send_telegram(f"✅ Content `{content_id[:8]}` auto-approved by NemoClaw.")
    return {"approved": True, "content_id": content_id}


def reject_content(content_id: str, reason: str = "Did not pass quality checks") -> dict:
    """Reject a content_queue item."""
    db = _db()
    db.table("content_queue").update({"status": "rejected"}).eq("id", content_id).execute()
    send_telegram(f"❌ Content `{content_id[:8]}` rejected.\nReason: {reason}")
    return {"rejected": True, "content_id": content_id}
```

---

## `nemoclaw/tools/update_strategy.py`

```python
from supabase import create_client
import os
import datetime

def _db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def update_strategy(notes: str) -> dict:
    """Write strategic notes that the Strategy Agent will read on its next run."""
    db = _db()
    db.table("agent_runs").insert({
        "agent_name": "nemoclaw_notes",
        "status": "success",
        "output_summary": notes[:500],
        "full_output": {"notes": notes, "type": "strategy_directive"},
        "started_at": datetime.datetime.utcnow().isoformat(),
        "finished_at": datetime.datetime.utcnow().isoformat(),
    }).execute()
    return {"noted": True}
```

---

## New Next.js File: `app/api/telegram-webhook/route.ts`

Receives Telegram callback query (button press from approval message).

```ts
import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase'
import { revalidatePath } from 'next/cache'

export async function POST(request: Request) {
  const body = await request.json()

  const callbackQuery = body?.callback_query
  if (!callbackQuery) return NextResponse.json({ ok: true })

  const data: string = callbackQuery.data ?? ''
  const [action, contentId] = data.split(':')

  if (action === 'approve') {
    await supabaseAdmin
      .from('content_queue')
      .update({ status: 'approved', approved_at: new Date().toISOString() })
      .eq('id', contentId)
    revalidatePath('/content')
    // Ack to Telegram
    await fetch(`https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ callback_query_id: callbackQuery.id, text: '✅ Approved' })
    })
  } else if (action === 'reject') {
    await supabaseAdmin
      .from('content_queue')
      .update({ status: 'rejected' })
      .eq('id', contentId)
    revalidatePath('/content')
    await fetch(`https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ callback_query_id: callbackQuery.id, text: '❌ Rejected' })
    })
  }

  return NextResponse.json({ ok: true })
}
```

### Register Telegram webhook (one-time setup after deploy)

```bash
curl -X POST "https://api.telegram.org/bot{TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-app.vercel.app/api/telegram-webhook"}'
```

---

## Daily Summary Telegram Message Format

The NemoClaw agent sends this every morning:

```
🎵 *NemoClaw Daily Report — Mon Mar 25 2026*

📈 *Top Video Today*
"3 Hours Dark Forest Rain" — 2,847 views, est. $4.20

📊 *Channel This Week*
Views: 14,200 | Watch Hours: 182h
Revenue: $48.60 | Subscribers: +12

🤖 *Agent Activity Yesterday*
✅ Analytics Agent — 6 videos processed
✅ Strategy Agent — picked "coffee shop ambiance" for next
⏳ Content Agent — 2 briefs in awaiting_approval

📋 *Today's Queue*
1x Production render scheduled
2x Uploads scheduled for 3PM

⚠️ *Warnings*
- "white noise" niche at 18% retention after 5 uploads → marked for kill
- Research Agent hasn't run in 7 days — recommend triggering today
```

---

## Celery Beat: Schedule NemoClaw Daily Summary

Add to `backend/tasks.py`:

```python
@celery_app.task(name="nemoclaw_daily_summary")
def nemoclaw_daily_summary():
    """Run every morning — builds the daily report and sends via Telegram."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'nemoclaw', 'tools'))
    from read_analytics import read_analytics
    from send_telegram import send_telegram
    import datetime

    channel = read_analytics("channel")
    videos = read_analytics("videos", limit=5)["videos"]
    runs = read_analytics("agent_runs", filters={}, limit=20)["runs"]

    # Build summary (simplified — NemoClaw agent will do this via LLM in full integration)
    top = videos[0] if videos else {}
    today = datetime.date.today().strftime("%a %b %d %Y")

    msg = f"""🎵 *NemoClaw Daily Report — {today}*

📈 *Top Video*
{top.get('title', 'N/A')} — {top.get('views', 0):,} views, est. ${top.get('estimated_revenue', 0):.2f}

📊 *Channel This Week*
Views: {channel.get('total_views', 0):,} | Watch Hours: {channel.get('total_watch_hours', 0):.0f}h
Revenue: ${channel.get('estimated_revenue', 0):.2f} | Subscribers: {channel.get('subscribers', 0)}

🤖 *Recent Agent Runs*
""" + "\n".join(
        f"{'✅' if r['status'] == 'success' else '❌'} {r['agent_name'].title()} — {r.get('output_summary', '')[:60]}"
        for r in runs[:5]
    )

    send_telegram(msg)

# Add to beat_schedule:
celery_app.conf.beat_schedule["nemoclaw-daily-8am"] = {
    "task": "nemoclaw_daily_summary",
    "schedule": crontab(hour=8, minute=0),
    "args": (),
}
```

---

## What Phase 5 Does NOT Include

- Full OpenClaw agent deployment (that requires NemoClaw account setup — out of scope for this subagent)
- Voice/video messages via Telegram
- Multi-user approval flows
- The NemoClaw tools here are designed to be run as standalone scripts or imported by the OpenClaw agent — the OpenClaw integration itself is configured externally after this phase is complete
