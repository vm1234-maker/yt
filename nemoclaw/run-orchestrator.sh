#!/usr/bin/env bash
# One-shot: trigger the NemoClaw parent agent (nemoclaw) with a JSON step list.
#
# Usage (from repo root):
#   ./nemoclaw/run-orchestrator.sh
#   ./nemoclaw/run-orchestrator.sh path/to/custom-steps.json
#
# Env file resolution (first match wins):
#   $NEMOCLAW_ENV_FILE
#   ~/.openclaw/workspace/.env.nemoclaw
#   ./backend/.env  (needs SUPABASE_*; NEMOCLAW_NEXT_APP_URL maps to NEXT_PUBLIC_APP_URL in CLI)
#
# Python: backend/.venv/bin/python if present, else python3
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STEPS_JSON="${1:-$ROOT/nemoclaw/orchestrator-default.json}"
if [[ ! -f "$STEPS_JSON" ]]; then
  echo "Steps file not found: $STEPS_JSON" >&2
  exit 1
fi

INPUT="$(cat "$STEPS_JSON")"

if [[ -n "${NEMOCLAW_ENV_FILE:-}" && -f "$NEMOCLAW_ENV_FILE" ]]; then
  ENV_FILE="$NEMOCLAW_ENV_FILE"
elif [[ -f "${HOME}/.openclaw/workspace/.env.nemoclaw" ]]; then
  ENV_FILE="${HOME}/.openclaw/workspace/.env.nemoclaw"
elif [[ -f "$ROOT/backend/.env" ]]; then
  ENV_FILE="$ROOT/backend/.env"
else
  echo "No env file found. Set NEMOCLAW_ENV_FILE or create ~/.openclaw/workspace/.env.nemoclaw or backend/.env" >&2
  exit 1
fi

if [[ -x "$ROOT/backend/.venv/bin/python" ]]; then
  PYTHON="$ROOT/backend/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

exec "$PYTHON" "$ROOT/nemoclaw/nemoclaw_cli.py" --env-file "$ENV_FILE" trigger-agent \
  --agent nemoclaw \
  --input "$INPUT"
