# NemoClaw — tool commands (sandbox)

Install the CLI once (from your **Mac**, project root):

```bash
./nemoclaw/install-to-sandbox.sh
```

That copies `nemoclaw_cli.py` to `~/.openclaw/nemoclaw_cli.py` and refreshes workspace markdown.

## Credentials

**Easiest (Mac):** push Supabase + the correct Next URL from `backend/.env` into the sandbox:

```bash
./nemoclaw/push-env-to-sandbox.sh
```

That writes `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `NEXT_PUBLIC_APP_URL`. By default the URL is `http://host.docker.internal:3000` (sandbox → Next on your Mac). If **`NEMOCLAW_NEXT_APP_URL`** is set in `backend/.env` (e.g. `https://your-app.vercel.app`), the sandbox uses that so **`trigger-agent`** hits your **deployed** app instead.

You do **not** need to copy OpenAI/Redis/YouTube into the sandbox for the CLI.

Or create **`~/.openclaw/workspace/.env.nemoclaw`** manually with real values:

- `SUPABASE_URL` — `https://….supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY` — service role (server only; never commit)
- `NEXT_PUBLIC_APP_URL` — **`http://host.docker.internal:3000`** so the sandbox can reach Next.js on the Mac

Paste example:

```bash
cat > ~/.openclaw/workspace/.env.nemoclaw << 'EOF'
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_KEY
NEXT_PUBLIC_APP_URL=http://host.docker.internal:3000
EOF
```

## CLI usage (JSON on stdout)

```bash
# Channel rollup
python3 ~/.openclaw/nemoclaw_cli.py read-analytics --type channel

# Recent videos
python3 ~/.openclaw/nemoclaw_cli.py read-analytics --type videos --limit 5

# Trigger backend agent (Next proxies to FastAPI)
python3 ~/.openclaw/nemoclaw_cli.py trigger-agent --agent analytics

# Parent orchestrator — run several agents in order (one parent run_id, child rows in agent_runs)
python3 ~/.openclaw/nemoclaw_cli.py trigger-agent --agent nemoclaw --input '{"steps":[{"agent":"research","input":{}},{"agent":"strategy","input":{}}]}'

# One command from repo root (uses nemoclaw/orchestrator-default.json + backend/.env or ~/.openclaw/...):
#   ./nemoclaw/run-orchestrator.sh
#   npm run nemoclaw:orchestrate
# Custom steps file: ./nemoclaw/run-orchestrator.sh path/to/steps.json

# Strategy note for next Strategy run
python3 ~/.openclaw/nemoclaw_cli.py update-strategy "Prioritize rain + lofi until Thursday"
```

## OpenClaw agent

Tell the model it may run these commands via **exec** when tools are enabled, or paste output into chat.

## Network policy

Supabase plus your Next.js origin(s) must be allowlisted in `nemoclaw/openclaw-sandbox.yaml` (local `host.docker.internal:3000` and, for production, your **Vercel hostname** on port 443). From the Mac, after editing the policy file:

`openshell policy set --policy nemoclaw/openclaw-sandbox.yaml yt-manager --wait`

## Production (Vercel + Railway)

1. **Vercel** project env: `BACKEND_URL` = your FastAPI origin (e.g. Railway) so `/api/run-agent` can proxy to the worker.
2. **`backend/.env`** on your machine: set `NEMOCLAW_NEXT_APP_URL=https://<your-deployment>.vercel.app`, then run `./nemoclaw/install-to-sandbox.sh` again so `.env.nemoclaw` gets the HTTPS URL.
3. **`openclaw-sandbox.yaml`**: ensure the `nextjs_vercel` block’s `host` matches that same hostname (edit if yours is not `yt-pi-ochre.vercel.app`), then reapply the policy (command above).
4. In the sandbox, test:  
   `python3 ~/.openclaw/nemoclaw_cli.py trigger-agent --agent research`  
   You should see a new row in **agent_runs** in Supabase and the dashboard.

## Dependencies (sandbox)

```bash
pip install supabase httpx
```

(`pypi` preset during `nemoclaw onboard` allows this.)
