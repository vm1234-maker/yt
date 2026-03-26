#!/usr/bin/env bash
# Updates only .env.nemoclaw from backend/.env. For a full install (CLI + markdown), use:
#   ./nemoclaw/install-to-sandbox.sh
exec "$(cd "$(dirname "$0")" && pwd)/install-to-sandbox.sh"
