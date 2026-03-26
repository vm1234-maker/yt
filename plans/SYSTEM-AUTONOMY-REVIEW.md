# System autonomy review — March 2025

This document reviews whether the codebase **autonomously posts YouTube videos** and **reports back via iMessage**, using the infrastructure described in the project rules and `plans/AUTONOMOUS-OPERATIONS.md`.

---

## Executive summary

| Goal | Status | Notes |
|------|--------|--------|
| End-to-end video → YouTube | **Implemented** | Pipeline + agents call Upload Agent with OAuth; requires valid `YOUTUBE_*` and channel. |
| Fully hands-off posting | **Configurable, not guaranteed** | `AUTO_APPROVE_AFTER_CONTENT` skips the approval gate; still needs workers, APIs, assets, quotas. |
| Scheduled analytics + metrics | **Implemented** | Celery Beat → `run_scheduled_agent` → Analytics Agent daily (4:00 UTC). |
| Scheduled strategy → Content | **Optional** | `AUTO_STRATEGY_WEEKLY=true` → Strategy Mondays 6:00 UTC; triggers Content via Next.js. |
| Daily iMessage report | **Partially implemented** | Task runs in Celery; **AppleScript only works on macOS**. Run **Celery Beat on the Mac** (not the Docker `beat` container) so `nemoclaw_daily_summary` can send iMessage. |
| NemoClaw “manages app + channel” | **Partially** | Sandbox CLI reads Supabase / triggers APIs; does not replace Celery or OAuth. |

**Verdict:** The **factory** can post and analyze on schedules **if** Docker, Next.js, Supabase, YouTube OAuth, and content prerequisites are satisfied. **True** “set and forget” operation is an **ops** achievement (uptime, quotas, review policy), not a single flag. **iMessage reporting** is **not** reliable from the default Docker-only worker setup.

---

## 1. Autonomous posting path

```
Celery Beat / manual API
  → FastAPI POST /api/run-agent or /api/run-pipeline
  → agent_runs row + Celery task
  → dispatch_agent() → agent modules
```

**Full pipeline** (`pipeline.run_full_pipeline`): Research → Brainstorm → Content → **[approval or AUTO_APPROVE]** → Production → Upload.

**Upload Agent** uses **YouTube Data API** with OAuth refresh token (`backend/config.py`, `tools/youtube_upload.py`). Without a channel and valid token, uploads cannot succeed.

**Gaps vs “posts by itself forever”**

- No automatic **pipeline** schedule in Beat by default — you trigger pipeline from UI/API or rely on Strategy → Content (not a full pipeline).
- **YouTube quotas**, **review**, and **errors** can stop runs; no automatic retry policy in code.
- **Pipeline** runs are **`agent_name: pipeline`** — the Agents dashboard cards only list the **six** named agents; pipeline history appears in `agent_runs` but not as its own card.

---

## 2. Scheduling layer (Celery Beat)

| Job | Task | Schedule (UTC) |
|-----|------|----------------|
| Analytics | `run_scheduled_agent` → `analytics` | Daily 04:00 |
| Strategy (if enabled) | `run_scheduled_agent` → `strategy` | Monday 06:00 |
| Daily summary | `nemoclaw_daily_summary` | Daily 08:00 |

`run_scheduled_agent` **inserts** an `agent_runs` row then enqueues `run_agent_task` (fixed from the earlier static-UUID bug).

**Config:** `AUTO_STRATEGY_WEEKLY`, `AUTO_APPROVE_AFTER_CONTENT` in `backend/config.py` / `.env`.

---

## 3. iMessage “report back”

**Implementation:** `backend/tasks.py` → `nemoclaw_daily_summary` → `nemoclaw/tools/read_analytics.py` + `send_imessage.py` (AppleScript).

**Reality:**

- **Docker `worker`/`beat` images are Linux** → no Messages / `osascript` → send fails; code **catches** and logs (`iMessage skipped`).
- For iMessage delivery, run Celery Beat **on macOS** (not the Docker `beat` container) with `IMESSAGE_RECIPIENT` set — see `plans/AUTONOMOUS-OPERATIONS.md`.

**Data in the message** depends on Supabase having analytics rows (`channel_metrics`, `video_analytics`).

---

## 4. NemoClaw (OpenShell sandbox)

- **Policy:** `nemoclaw/openclaw-sandbox.yaml` — Supabase, PyPI, Next.js host, etc.
- **CLI:** `nemoclaw/nemoclaw_cli.py` — read analytics, trigger agents.
- **Role:** Orchestration and monitoring **alongside** the app, not inside Celery.

Does **not** by itself upload videos or fill `channel_metrics`; it triggers **your** APIs and reads **your** DB.

---

## 5. Dashboard & “real time”

- **Dashboard** (`app/dashboard/page.tsx`) loads `agent_runs` **once** per server render for the header badge. **`components/nav.tsx`** subscribes to Realtime for running dots — that part was already live.
- **Agents page** (`app/agents/page.tsx`) is a **Server Component**; it only re-fetches when you **navigate** or **refresh the browser**. Previously, **`LiveAgentCard`** subscribed only to **UPDATE** on the **first** run’s UUID, so when a **new** run started for the same agent, the card kept showing the **old** run and **stale** RUNS / SUCCESS / AVG TIME.
- **Fix (implemented in `components/live-agent-card.tsx`):**
  - Realtime on `agent_runs` with `filter: agent_name=eq.<agent>` for **all** events (INSERT/UPDATE).
  - On each event, **refetch** `GET /api/agents` and recompute **latest run + aggregate stats** client-side.
  - **Poll every 5s** while `status === 'running'` as a fallback if Realtime lags.
- **Pipeline** runs use `agent_name: pipeline` — they do **not** appear on the six agent cards; use **Activity** / DB / `agent_runs` for pipeline rows.

---

## 6. Schema / metrics caveats

- **`channel_metrics`:** Migration `002` renames `subscribers` → `subscribers_gained` and adds `total_subscribers`. Some UI still references `subscribers`; align types and queries if dashboards show wrong/zero subscribers.
- **Empty tables:** Until Analytics runs successfully with eligible videos, NemoClaw `read-analytics --type channel` returns `{}`.

---

## 7. Checklist: “are we autonomous?”

- [ ] YouTube channel created; OAuth refresh token in `backend/.env`
- [ ] `docker compose` **api + worker + beat** running; Next.js on **:3000** with `host.docker.internal` for workers if applicable
- [ ] At least one successful **pipeline or agent chain** to upload
- [ ] `AUTO_*` flags set intentionally
- [ ] iMessage: run summary task **on Mac** or change notifier
- [ ] Monitor `agent_runs` for stuck `running` rows after crashes

---

## 8. Conclusion

The **infrastructure** supports autonomous **scheduling**, **posting** (via agents + OAuth), and **intended** daily summaries. **Full autonomy** in production means **you** keep workers alive, credentials valid, and policies (auto-approve, strategy) aligned with risk tolerance. **iMessage** from Docker is **not** a complete solution without a macOS-side runner or alternative transport.
