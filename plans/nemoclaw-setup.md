# NemoClaw Setup Guide — YouTube Automation Manager

> Run this after the backend is working and at least one Content Agent run has completed.
> Time to complete: ~15 minutes.

---

## Prerequisites Checklist

- [x] Docker Desktop running
- [x] Node.js v24 installed (requires ≥ v20)
- [x] Backend containers running (`docker compose up -d` in `/backend`)
- [x] Dashboard running (`npm run dev` in project root)
- [ ] **NVIDIA API key** — get yours free at https://build.nvidia.com → Profile → API Keys
- [ ] **OpenAI credits** — add at least $5 at https://platform.openai.com/settings/billing (for backend agents)

---

## Step 1 — Get Your Free NVIDIA API Key

1. Go to https://build.nvidia.com
2. Create a free account (or log in)
3. Click your profile → **API Keys** → **Generate API Key**
4. Copy and save it — you'll need it in Step 3

The key starts with `nvapi-...`. This is separate from your OpenAI key.
NemoClaw uses this to call NVIDIA's Nemotron models (120B parameter model — completely free).

---

## Step 2 — Install NemoClaw

Run this single command in your terminal:

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
```

This will:
- Install OpenShell (the secure sandbox runtime)
- Install the `nemoclaw` CLI globally via npm
- Start the onboarding wizard automatically

If `nemoclaw` isn't found after install, run:
```bash
source ~/.zshrc
```

---

## Step 3 — Onboard: Create Your Sandbox

The wizard will ask three things:

### Sandbox name
```
> yt-manager
```

### NVIDIA API key
```
> nvapi-YOUR-KEY-HERE
```

### Policy presets
Type `list` to see options. Select these presets by pressing space:
```
> pypi npm
```
(We'll apply our custom Supabase + backend policy separately in Step 5.)

The wizard builds the sandbox image (~2.4 GB, takes 2–5 minutes).
When done, you'll see:

```
──────────────────────────────────────────────────
Sandbox      yt-manager (Landlock + seccomp + netns)
Model        nvidia/nemotron-3-super-120b-a12b (NVIDIA Cloud API)
──────────────────────────────────────────────────
Run:         nemoclaw yt-manager connect
```

---

## Step 4 — Verify the Sandbox Is Running

```bash
nemoclaw yt-manager status
```

You should see `running`. Now connect and do a quick test:

```bash
nemoclaw yt-manager connect
```

This drops you into the sandbox shell: `sandbox@yt-manager:~$`

Test the agent:
```bash
openclaw agent --agent main --local -m "hello" --session-id test
```

You should get a response from Nemotron 3 Super 120B. Type `exit` to leave the sandbox.

---

## Step 5 — Apply Our Custom Network Policy

From your project root (outside the sandbox):

```bash
openshell policy set nemoclaw/openclaw-sandbox.yaml
```

This allows the sandbox to call:
- Supabase (read analytics, write agent logs)
- Our local Next.js API (trigger agent runs)
- NVIDIA inference endpoint (required for the model)

Verify the policy was applied:
```bash
nemoclaw yt-manager status
```

---

## Step 6 — Load Our Agent Instructions

Connect to the sandbox and configure the system prompt:

```bash
nemoclaw yt-manager connect
```

Inside the sandbox, copy the agent instructions into the OpenClaw config:
```bash
cat /app/nemoclaw/agent-instructions.md | openclaw config set-system-prompt --agent main
```

If that command isn't available, you can paste the instructions via the TUI:
```bash
openclaw tui
```
Then in the TUI, go to Settings → System Prompt and paste the contents of `nemoclaw/agent-instructions.md`.

Exit the sandbox:
```bash
exit
```

---

## Step 7 — Copy Our Python Tools into the Sandbox

From your project root:

```bash
# Create the tools directory in the sandbox
nemoclaw yt-manager connect -- mkdir -p /home/user/tools

# Copy our NemoClaw tools into the sandbox
for f in nemoclaw/tools/*.py; do
  nemoclaw yt-manager connect -- bash -c "cat > /home/user/tools/$(basename $f)" < "$f"
done
```

---

## Step 8 — Test the Full Integration

Connect to the sandbox and send a test command:

```bash
nemoclaw yt-manager connect
openclaw agent --agent main --local -m "Read the latest analytics and tell me what you see" --session-id test-1
```

NemoClaw will:
1. Call `read_analytics` tool → hits Supabase
2. Parse the data
3. Return a summary

If it works, the integration is live.

---

## Step 9 (Optional) — Switch to a Larger Model

The default Nemotron 3 Super 120B is already excellent, but you can switch:

```bash
# Outside the sandbox
openshell inference set --provider nvidia-nim --model nvidia/llama-3.1-nemotron-ultra-253b-v1
```

Available models:
| Model | Size | Best for |
|---|---|---|
| `nvidia/nemotron-3-super-120b-a12b` | 120B | Default — fast + smart |
| `nvidia/llama-3.1-nemotron-ultra-253b-v1` | 253B | Deep analysis |
| `nvidia/llama-3.3-nemotron-super-49b-v1.5` | 49B | Faster responses |

---

## Daily Operations

### Start NemoClaw (after reboots)
```bash
nemoclaw yt-manager connect
```
The sandbox keeps running in the background. `connect` just opens a session.

### Check sandbox status
```bash
nemoclaw yt-manager status
```

### View sandbox logs
```bash
nemoclaw my-assistant logs --follow
```
(Use the actual sandbox name: `yt-manager`)
```bash
nemoclaw yt-manager logs --follow
```

### Chat with the agent
```bash
nemoclaw yt-manager connect
openclaw tui
```

---

## What NemoClaw Does Automatically

NemoClaw runs the `nemoclaw_daily_summary` Celery Beat task every morning at 8am.
This task reads Supabase and sends an iMessage to `+17705192836` (configured in `backend/.env`).

NemoClaw the agent handles:
- Analyzing the analytics report and deciding which niche to focus on next
- Auto-approving content that passes the quality checks (RPM ≥ $8, good title format)
- Asking you via iMessage if a video needs human review
- Sending an iMessage alert if an agent run fails

---

## Troubleshooting

### `nemoclaw: command not found` after install
```bash
source ~/.zshrc   # or ~/.bashrc
```

### Sandbox won't start on Mac
NemoClaw on macOS requires Docker Desktop (not Podman).
Make sure Docker Desktop is running, then:
```bash
nemoclaw yt-manager status
```

### Can't reach localhost:3000 from inside sandbox
The sandbox uses its own network namespace. Use `host.docker.internal` instead of `localhost`:

Update `nemoclaw/openclaw-sandbox.yaml`:
```yaml
- endpoints:
    - host: host.docker.internal
      port: 3000
```
Then reapply: `openshell policy set nemoclaw/openclaw-sandbox.yaml`

Also update `backend/.env`:
```
NEXT_PUBLIC_APP_URL=http://host.docker.internal:3000
```

### Policy not taking effect
Dynamic policy changes only last until the sandbox stops.
To make them permanent, edit `nemoclaw/openclaw-sandbox.yaml` and re-run:
```bash
nemoclaw onboard
```