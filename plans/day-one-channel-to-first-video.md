# Day one: new channel → first video live

Use this as a single ordered checklist. Assumes repo is cloned and `.env` files exist.

---

## Before you have a channel

You can still run: Supabase, Next.js, Docker backend, NemoClaw sandbox, Research/Content/Production to files in DB. **Uploading and real analytics need a channel + OAuth.**

---

## 1. Create the channel

1. Sign in to YouTube with the **Google account** you will use for this brand long-term.
2. Create a **channel** (brand channel is fine). Pick a name you can reuse.
3. **Use the same account** for everything below (OAuth, uploads, Analytics).

---

## 2. Google Cloud → OAuth for this app

1. [Google Cloud Console](https://console.cloud.google.com/) → project → **APIs & Services** → enable **YouTube Data API v3** and **YouTube Analytics API**.
2. **OAuth consent screen** (External or Internal as appropriate) → add scopes for YouTube upload + YouTube + Analytics (match `backend/tools/youtube_auth.py`).
3. **Credentials** → OAuth 2.0 Client ID (Desktop app or Web with redirect `http://localhost:9000/`).
4. Copy **Client ID** and **Client secret** into `backend/.env` as `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET`.

---

## 3. Refresh token (one-time, on your Mac)

```bash
cd backend && python3 tools/youtube_auth.py
```

If dependencies are missing: `pip3 install google-auth-oauthlib google-auth-httplib2` (or use the backend Docker/venv environment).

Paste the printed `YOUTUBE_REFRESH_TOKEN` into `backend/.env`. Sign in with the **same Google account** that owns the channel.

Restart Docker after changing `.env`:

```bash
docker compose up -d --build
```

---

## 4. App stack running

| Service | Command / note |
|--------|------------------|
| Supabase | Project live; migrations applied |
| Backend | `cd backend && docker compose up -d` |
| Next.js | `npm run dev` (port **3000** if workers use `host.docker.internal:3000`) |

---

## 5. NemoClaw (manager)

1. Sandbox `yt-manager` running; policy applied: `openshell policy set --policy nemoclaw/openclaw-sandbox.yaml yt-manager --wait`
2. From repo root: `./nemoclaw/push-env-to-sandbox.sh`
3. In sandbox: venv + `pip install supabase httpx`; test `nemoclaw_cli.py read-analytics`
4. Load agent instructions: `plans/nemoclaw-setup.md` Step 6 (`nemoclaw/agent-instructions.md` → system prompt)

---

## 6. First publish path

1. Open dashboard → run **full pipeline** or **POST `/api/run-pipeline`** (or step agents manually: research → content → approval if not auto-approved → production → upload).
2. Confirm row in **`content_queue`** and success in **`agent_runs`**.
3. Confirm video appears in **YouTube Studio** for that channel.

---

## 7. After first video

- **Analytics Agent** (scheduled or manual) can populate `video_analytics` / `channel_metrics`.
- **Celery Beat** jobs apply per `backend/tasks.py` + your `.env` flags.
- **NemoClaw** continues to read Supabase and trigger `/api/run-agent` as configured.

---

## Troubleshooting

| Symptom | Check |
|--------|--------|
| Upload fails | OAuth token; same Google account as channel; API quotas |
| Worker can’t trigger Next.js | `NEXT_PUBLIC_APP_URL` reachable from Docker (`host.docker.internal:3000` on Mac) |
| Analytics empty | Videos uploaded + `youtube_video_id` on `content_queue`; Analytics API enabled |
