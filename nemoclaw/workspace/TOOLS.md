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

That writes only `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `NEXT_PUBLIC_APP_URL=http://host.docker.internal:3000` (you do **not** need to copy OpenAI/Redis/YouTube into the sandbox for the CLI).

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

# Strategy note for next Strategy run
python3 ~/.openclaw/nemoclaw_cli.py update-strategy "Prioritize rain + lofi until Thursday"
```

## OpenClaw agent

Tell the model it may run these commands via **exec** when tools are enabled, or paste output into chat.

## Network policy

Supabase + `host.docker.internal:3000` must be allowlisted: from Mac run  
`openshell policy set --policy nemoclaw/openclaw-sandbox.yaml yt-manager --wait`

## Dependencies (sandbox)

```bash
pip install supabase httpx
```

(`pypi` preset during `nemoclaw onboard` allows this.)
