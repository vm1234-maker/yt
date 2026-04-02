#!/usr/bin/env python3
"""
Send a one-line test iMessage (macOS only).

Usage (from repo):
  cd backend && .venv/bin/python scripts/test_imessage.py

Requires backend/.env with IMESSAGE_RECIPIENT=+1XXXXXXXXXX (E.164).
First run: allow Terminal/Python to control Messages (System Settings → Privacy → Automation).
"""
from __future__ import annotations

import sys
from pathlib import Path

# backend/ as cwd for config + tools
_backend = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_backend))

from config import settings  # noqa: E402
from tools.imessage_tool import send_imessage  # noqa: E402


def main() -> None:
    if not settings.IMESSAGE_RECIPIENT:
        print("Set IMESSAGE_RECIPIENT in backend/.env (E.164, e.g. +17705551234).", file=sys.stderr)
        sys.exit(2)
    out = send_imessage("NemoClaw — iMessage test OK. Daily digest uses this same path.")
    print(out)


if __name__ == "__main__":
    main()
