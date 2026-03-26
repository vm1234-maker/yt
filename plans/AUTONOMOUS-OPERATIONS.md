# Autonomous channel operations — plan & controls

This doc ties together **NemoClaw**, **Celery Beat**, **agents**, and **human gates** so you know what “full autonomy” means and how to turn knobs safely.

---

## Architecture (who does what)

| Layer | Role |
|--------|------|
| **NemoClaw (sandbox)** | Reads Supabase via CLI/tools, triggers Next.js `POST /api/run-agent` — **orchestration**, not the data pipeline itself. |
| **Next.js** | Dashboard + API routes that proxy to FastAPI (`BACKEND_URL`) for agent/pipeline runs. |
| **FastAPI + Celery** | **Execution**: agents write to Supabase, pipeline runs production/upload. |
| **Celery Beat** | **Schedules**: daily Analytics (4am), daily summary task (8am), optional weekly Strategy (Mon 6am if enabled). |
| **Supabase** | **Source of truth** for metrics (`channel_metrics`, `video_analytics`), queue, `agent_runs`. |

**NemoClaw does not fill `channel_metrics` by itself.** The **Analytics Agent** (scheduled or manual) pulls YouTube Analytics and inserts rows. Empty `read-analytics --type channel` until at least one successful analytics run **and** videos in `content_queue` with status `scheduled`/`uploaded` and a `youtube_video_id`.

---

## Autonomy tiers

### Tier A — Observability only (safest)
- Docker: `api`, `worker`, `beat` running; YouTube OAuth + Supabase configured.
- **Fixed**: Beat calls `run_scheduled_agent` so each analytics run gets a real `agent_runs` row (previously broken).
- `channel_metrics` populates after Analytics runs with eligible videos.

### Tier B — Scheduled strategy (ideation → Content Agent)
- Set in `backend/.env`: `AUTO_STRATEGY_WEEKLY=true`
- Restart **beat** (and worker). Mondays **06:00** UTC (adjust in `tasks.py` if you want local time), Strategy runs and **POSTs** to `NEXT_PUBLIC_APP_URL` `/api/run-agent` for **content** with chosen niche/angle.
- Requires Next.js reachable from the **worker** at `NEXT_PUBLIC_APP_URL` (e.g. `http://host.docker.internal:3000` on Mac Docker).

### Tier C — Full pipeline without dashboard approval (use carefully)
- Set `AUTO_APPROVE_AFTER_CONTENT=true` in `backend/.env`.
- **Full pipeline** auto-sets `content_queue` to `approved` after Content and continues to Production → Upload.
- **Risk**: publishes without you reviewing the brief in the UI. Enable only when you trust titles/thumbnails/metadata rules.

### Tier D — NemoClaw “manager”
- Policy + sandbox CLI working; can trigger agents and read analytics.
- **Does not** replace Beat; it complements (alerts, approvals, ad-hoc triggers).

---

## Required checklist for “hands-off” YouTube ops

1. **Backend** `.env`: Supabase, Redis, YouTube OAuth refresh token, `OPENAI_API_KEY`, `NEXT_PUBLIC_APP_URL` for Strategy/pipeline triggers from Docker, `IMESSAGE_RECIPIENT` for daily digest.
2. **`docker compose up -d`** (or equivalent): `api` + `worker`. For **iMessage** digests, run **Celery Beat on your Mac** (same repo, same `.env`) — AppleScript cannot send from the Linux `beat` container.
3. **At least one video path**: `content_queue` rows with `youtube_video_id` and status `scheduled` or `uploaded` so Analytics has something to measure.
4. **Migration 002** applied in Supabase if you use `subscribers_gained` / `niche` columns (`002_pipeline_and_analytics.sql`).
5. **Optional**: `AUTO_STRATEGY_WEEKLY`, `AUTO_APPROVE_AFTER_CONTENT` as above.
6. **iMessage daily summary**: `nemoclaw_daily_summary` uses AppleScript only — the **Celery worker** that executes this task must run on **macOS** with Messages (not the Linux Docker worker). In practice: run a **worker on your Mac** with the same Redis broker, or only enqueue digest to a Mac worker (advanced). Grant Terminal automation access to Messages if prompted.

### macOS host venv — use Python 3.11

Apple’s default `python3` is often **3.9**; `pip` then cannot install **`crewai==0.80.0`** (needs 3.10+). Match Docker’s **3.11**:

```bash
brew install python@3.11
# Celery Beat’s schedule file uses dbm.gnu — required on macOS Homebrew Python:
brew install python-gdbm@3.11
cd backend
/opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If Beat errors with `db type is dbm.gnu, but the module is not available`, run `brew install python-gdbm@3.11`, delete `backend/celerybeat-schedule*` (or let Beat recreate after fix), and start again.

On Intel Macs, Homebrew may use `/usr/local/opt/python@3.11/bin/python3.11`. Then:

```bash
celery -A tasks beat --loglevel=info
# and/or worker on Mac if this process should send iMessage
celery -A tasks worker --loglevel=info
```

---

## Manual tests

```bash
# From host — trigger analytics once (creates run row + processes)
curl -s -X POST "$BACKEND_URL/api/run-agent" -H "Content-Type: application/json" \
  -d '{"agent":"analytics","input":{}}'

# Or dashboard Agents page / your existing UI
```

After success, `channel_metrics` should have a row (if rollup API succeeds) and NemoClaw `read-analytics --type channel` returns non-empty JSON.

---

## Files touched for scheduling fix

- `backend/tasks.py` — `run_scheduled_agent`, Beat entries, safe iMessage failure in `nemoclaw_daily_summary`
- `backend/config.py` — `AUTO_STRATEGY_WEEKLY`, `AUTO_APPROVE_AFTER_CONTENT`
- `backend/pipeline.py` — optional auto-approve after Content
