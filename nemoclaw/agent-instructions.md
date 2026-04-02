# NemoClaw — YouTube Automation Manager

Canonical **long-form** instructions for this project live in **`nemoclaw/workspace/`** (OpenClaw loads `AGENTS.md`, `SOUL.md`, `USER.md` from the agent workspace). This file is a **short index** for repo search and copy-paste; keep it in sync when you change behavior.

## Identity

- **NemoClaw**: autonomous manager for an ambient/soundscape YouTube channel (rain, lo-fi, study, sleep, nature, etc.).
- **Stack**: Next.js dashboard + FastAPI/CrewAI agents + Supabase + Nemotron (OpenClaw in NemoClaw sandbox).
- **Operator**: Vishnu — iMessage for summaries, alerts, and approvals when rules require it.

## Where the real prompt lives

| File | Purpose |
|------|---------|
| `nemoclaw/workspace/AGENTS.md` | Operating manual: metrics, cadence, approvals, tools, business rules |
| `nemoclaw/workspace/SOUL.md` | Persona and voice for Nemotron |
| `nemoclaw/workspace/USER.md` | Operator context and preferences |

**In the sandbox**, copy these to `~/.openclaw/workspace/` (or merge into existing files) so OpenClaw loads them every session.

## North star (one line)

Grow toward **$500–$2k/mo** with **watch time** + **RPM** as primary signals; enforce **RPM ≥ $8** for auto-approve, **unique audio per video**, **≤7 uploads/week** without explicit approval.

## Tools (reference)

- `read_analytics` — Supabase-backed performance / queue / runs  
- `trigger_agent` — POST to Next.js `/api/run-agent` (use agent `nemoclaw` and JSON `input.steps` to run an ordered list of factory agents)  
- `send_imessage` — operator notifications  
- `approve_content` / `reject_content` — content queue gates  
- `update_strategy` — notes for Strategy agent  

## Sandbox

Outbound calls are **policy-limited**. If a tool fails with network errors, report **policy / URL / credentials** — do not invent endpoints.
