# Autonomy implementation plan (executed)

This document records what was **planned** and **implemented** to close gaps identified in `plans/SYSTEM-AUTONOMY-REVIEW.md`.

---

## Goals

1. **Daily report back via iMessage** — `nemoclaw_daily_summary` sends only through **AppleScript → Messages** (`IMESSAGE_RECIPIENT`). **Beat must run on macOS** (see below).
2. **Channel metrics schema** — Align UI and digest with migration `002` (`total_subscribers`, `subscribers_gained`).
3. **Pipeline visibility** — Show **Full Pipeline** on the agents dashboard with live stats and a trigger.
4. **Optional scheduled full pipeline** — `AUTO_PIPELINE_WEEKLY` (off by default; Sundays 10:00 UTC).

---

## Implemented

### 1. iMessage-only daily digest

- **Files:** `backend/tasks.py` (`nemoclaw_daily_summary`, `_send_daily_digest_imessage`), `nemoclaw/tools/send_imessage.py`.
- **Behavior:** Builds the report from Supabase; sends with **iMessage only** if `IMESSAGE_RECIPIENT` is set.
- **Critical:** **Do not rely on Docker’s `beat` service** for iMessage. Run Beat on the **Mac host**:
  ```bash
  cd backend && source .venv/bin/activate  # or your venv
  celery -A tasks beat --loglevel=info
  ```
  Keep Docker `api` + `worker` as usual. Optionally **disable** the `beat` service in `docker-compose.yml` if you only use host Beat, to avoid duplicate schedules.

### 2. Subscriber fields

- **Files:** `lib/types.ts` (`ChannelMetrics`), `lib/channel-metrics.ts` (`displaySubscriberCount`), `app/dashboard/page.tsx`, `app/analytics/page.tsx`, `backend/tasks.py` (`_subscriber_line` in digest).
- **Behavior:** Prefer `total_subscribers`, then legacy `subscribers`, then `subscribers_gained` for display.

### 3. Pipeline on Agents page

- **Files:** `app/agents/page.tsx` (pipeline in `AGENT_META`), `components/live-agent-card.tsx` (pipeline trigger), `components/run-pipeline-mini-button.tsx`, `components/agent-status-grid.tsx`.
- **Behavior:** Seventh card **Full Pipeline**; play button calls **`POST /api/run-pipeline`**; realtime refresh unchanged (filters `agent_name=eq.pipeline`).

### 4. Scheduled weekly pipeline

- **Files:** `backend/config.py` (`AUTO_PIPELINE_WEEKLY`), `backend/tasks.py` (`run_scheduled_pipeline`, Beat entry `pipeline-weekly-sun-10am-utc`).
- **Behavior:** When `AUTO_PIPELINE_WEEKLY=true`, Beat enqueues a **full pipeline** run every **Sunday 10:00 UTC**. Requires workers, Next.js reachable, OAuth, and assets; **combine with `AUTO_APPROVE_AFTER_CONTENT` only if you accept unattended uploads.**

---

## Operations checklist

- [ ] `IMESSAGE_RECIPIENT` set in `backend/.env` (E.164, e.g. `+1XXXXXXXXXX`).
- [ ] Beat for schedules that include iMessage runs **on macOS**, not in the Linux `beat` container.
- [ ] Restart `worker` after env changes; restart host Beat when changing `.env`.
- [ ] Leave `AUTO_PIPELINE_WEEKLY=false` until you are ready for weekly unattended pipeline runs.

---

## Related docs

- `plans/SYSTEM-AUTONOMY-REVIEW.md` — architecture verdict and gaps.
- `plans/AUTONOMOUS-OPERATIONS.md` — tiers and env flags.
