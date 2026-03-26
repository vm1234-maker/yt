#!/usr/bin/env bash
# Run on your Mac from the project root — uses `openshell sandbox upload` (reliable).
#
#   /sandbox/.openclaw/nemoclaw_cli.py
#   /sandbox/.openclaw/workspace/*  (from nemoclaw/workspace/)
#   /sandbox/.openclaw/workspace/.env.nemoclaw  (Supabase + host.docker.internal from backend/.env)
#
# Usage:
#   ./nemoclaw/install-to-sandbox.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SB_NAME="${NEMOCLAW_SANDBOX:-yt-manager}"
cd "$ROOT"

command -v openshell >/dev/null 2>&1 || { echo "openshell not found"; exit 1; }

ENV_OUT="/tmp/.env.nemoclaw"
SSH_CFG=""
trap 'rm -f "$ENV_OUT" ${SSH_CFG:+"$SSH_CFG"}' EXIT

python3 << PY
from pathlib import Path
root = Path("$ROOT")
text = (root / "backend" / ".env").read_text(encoding="utf-8")
out = {}
nemoclaw_next = None
for line in text.splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    k, v = k.strip(), v.strip().strip('"').strip("'")
    if k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        out[k] = v
    if k == "NEMOCLAW_NEXT_APP_URL" and v:
        nemoclaw_next = v.rstrip("/")
if len(out) != 2:
    raise SystemExit("backend/.env must define SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
out["NEXT_PUBLIC_APP_URL"] = nemoclaw_next or "http://host.docker.internal:3000"
body = "".join(f"{k}={v}\n" for k, v in out.items())
Path("$ENV_OUT").write_text(body, encoding="utf-8")
print("→ Wrote", len(body), "bytes to", "$ENV_OUT")
PY

# A bad upload can leave nemoclaw_cli.py as a directory; tar then fails with "File exists".
# Non-interactive SSH is reliable (nemoclaw connect -- … is not).
SSH_CFG="$(mktemp)"
openshell sandbox ssh-config "$SB_NAME" > "$SSH_CFG"
SSH_HOST="$(awk '/^Host / {print $2; exit}' "$SSH_CFG")"
if [[ -n "$SSH_HOST" ]] && command -v ssh >/dev/null 2>&1; then
  echo "→ Removing stale /sandbox/.openclaw/nemoclaw_cli.py (if any)..."
  ssh -F "$SSH_CFG" -o BatchMode=yes -o ConnectTimeout=20 "$SSH_HOST" \
    'rm -rf /sandbox/.openclaw/nemoclaw_cli.py' || true
else
  echo "→ (skip SSH cleanup: no ssh or empty Host from openshell sandbox ssh-config)"
fi

echo "→ Uploading to sandbox ${SB_NAME}..."
openshell sandbox upload "$SB_NAME" "$ROOT/nemoclaw/nemoclaw_cli.py" /sandbox/.openclaw/
openshell sandbox upload "$SB_NAME" "$ROOT/nemoclaw/requirements-sandbox.txt" /sandbox/.openclaw/
openshell sandbox upload "$SB_NAME" "$ROOT/nemoclaw/nemoclaw-run.sh" /sandbox/.openclaw/
openshell sandbox upload "$SB_NAME" "$ROOT/nemoclaw/workspace" /sandbox/.openclaw/workspace
openshell sandbox upload "$SB_NAME" "$ENV_OUT" /sandbox/.openclaw/workspace/

if [[ -n "$SSH_HOST" ]] && command -v ssh >/dev/null 2>&1; then
  echo "→ Creating venv + installing nemoclaw_cli deps (supabase, httpx)..."
  ssh -F "$SSH_CFG" -o BatchMode=yes -o ConnectTimeout=60 "$SSH_HOST" bash -s << 'REMOTE'
set -euo pipefail
mkdir -p /sandbox/.venvs
python3 -m venv /sandbox/.venvs/nemo
/sandbox/.venvs/nemo/bin/pip install -q --upgrade pip
/sandbox/.venvs/nemo/bin/pip install -q -r /sandbox/.openclaw/requirements-sandbox.txt
chmod +x /sandbox/.openclaw/nemoclaw-run.sh
echo "→ venv ready at /sandbox/.venvs/nemo"
REMOTE
else
  echo "→ (skip venv install: no ssh — run manually in sandbox, see nemoclaw/workspace/TOOLS.md)"
fi

echo "→ Done."
echo "    In sandbox:"
echo "      /sandbox/.openclaw/nemoclaw-run.sh read-analytics --type channel"
echo "    Or: /sandbox/.venvs/nemo/bin/python /sandbox/.openclaw/nemoclaw_cli.py read-analytics --type channel"
