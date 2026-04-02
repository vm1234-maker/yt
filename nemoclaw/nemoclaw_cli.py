#!/usr/bin/env python3
"""
NemoClaw — single-file CLI for Supabase + Next.js tools inside the OpenShell sandbox.

Usage:
  python3 nemoclaw_cli.py --help
  python3 nemoclaw_cli.py read-analytics --type channel
  python3 nemoclaw_cli.py trigger-agent --agent analytics
  python3 ~/.openclaw/nemoclaw_cli.py read-analytics --type channel

Env file (default ~/.openclaw/workspace/.env.nemoclaw):
  SUPABASE_URL              — project URL (https://xxx.supabase.co)
  SUPABASE_SERVICE_ROLE_KEY — service role key
  NEXT_PUBLIC_APP_URL       — http://host.docker.internal:3000 (local) or https://YOUR_APP.vercel.app
                              (must be allowlisted in openclaw-sandbox.yaml; set NEMOCLAW_NEXT_APP_URL
                              in backend/.env when running install-to-sandbox.sh for production)
  IMESSAGE_RECIPIENT        — optional; iMessage only works on macOS host, not Linux sandbox
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from typing import Any, Literal, Optional


def load_env_file(path: str) -> None:
    if not path or not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    # backend/.env often sets BOTH NEXT_PUBLIC_APP_URL (Docker → Next) AND NEMOCLAW_NEXT_APP_URL
    # (Vercel). For nemoclaw_cli on the Mac host, prefer Vercel — host.docker.internal is not
    # resolvable from a normal shell (ConnectError: nodename nor servname not known).
    nemo = os.environ.get("NEMOCLAW_NEXT_APP_URL", "").strip()
    if nemo:
        os.environ["NEXT_PUBLIC_APP_URL"] = nemo.rstrip("/")


def _require_supabase_env() -> None:
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        sys.stderr.write(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY. "
            "Create ~/.openclaw/workspace/.env.nemoclaw (see nemoclaw/workspace/.env.nemoclaw.example).\n"
        )
        sys.exit(2)


def _db():
    from supabase import create_client

    _require_supabase_env()
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def cmd_read_analytics(args: argparse.Namespace) -> dict[str, Any]:
    t = args.type
    limit = args.limit
    filters = json.loads(args.filters) if args.filters else None
    db = _db()

    if t == "channel":
        result = db.table("channel_metrics").select("*").order("recorded_at", desc=True).limit(1).execute()
        return result.data[0] if result.data else {}

    if t == "videos":
        q = db.table("video_analytics").select("*").order("recorded_at", desc=True)
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        return {"videos": q.limit(limit).execute().data or []}

    if t == "content_queue":
        q = db.table("content_queue").select("*").order("created_at", desc=True)
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        return {"queue": q.limit(limit).execute().data or []}

    if t == "agent_runs":
        q = db.table("agent_runs").select("*").order("started_at", desc=True)
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        return {"runs": q.limit(limit).execute().data or []}

    if t == "research":
        result = (
            db.table("agent_runs")
            .select("full_output")
            .eq("agent_name", "research")
            .eq("status", "success")
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0].get("full_output", {}).get("result", {})
        return {}

    return {}


def cmd_trigger_agent(args: argparse.Namespace) -> dict[str, Any]:
    import httpx

    app_url = os.environ.get("NEXT_PUBLIC_APP_URL", "http://host.docker.internal:3000")
    inp = json.loads(args.input) if args.input else {}
    r = httpx.post(
        f"{app_url.rstrip('/')}/api/run-agent",
        json={"agent": args.agent, "input": inp},
        headers={"Content-Type": "application/json"},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()


def _notify_imessage(message: str) -> dict[str, Any]:
    to = os.environ.get("IMESSAGE_RECIPIENT", "")
    if not to:
        return {"sent": False, "reason": "IMESSAGE_RECIPIENT not set"}
    if sys.platform != "darwin":
        return {"sent": False, "reason": "iMessage only available on macOS host (not Linux sandbox)"}
    safe_msg = message.replace('"', '\\"').replace("'", "\\'")
    script = f'''
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "{to}" of targetService
    send "{safe_msg}" to targetBuddy
end tell
'''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return {"sent": False, "error": result.stderr}
    return {"sent": True, "recipient": to}


def cmd_approve_content(args: argparse.Namespace) -> dict[str, Any]:
    db = _db()
    cid = args.content_id
    db.table("content_queue").update(
        {
            "status": "approved",
            "approved_at": _dt.datetime.utcnow().isoformat(),
        }
    ).eq("id", cid).execute()
    app_url = os.environ.get("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
    _notify_imessage(
        f"✅ Content {cid[:8]} auto-approved by NemoClaw.\n\nApprove/reject at: {app_url}/content"
    )
    return {"approved": True, "content_id": cid}


def cmd_reject_content(args: argparse.Namespace) -> dict[str, Any]:
    db = _db()
    cid = args.content_id
    reason = args.reason
    db.table("content_queue").update({"status": "rejected"}).eq("id", cid).execute()
    app_url = os.environ.get("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
    _notify_imessage(
        f"❌ Content {cid[:8]} rejected.\nReason: {reason}\n\nApprove/reject at: {app_url}/content"
    )
    return {"rejected": True, "content_id": cid}


def cmd_update_strategy(args: argparse.Namespace) -> dict[str, Any]:
    db = _db()
    notes = args.notes
    db.table("agent_runs").insert(
        {
            "agent_name": "nemoclaw_notes",
            "status": "success",
            "output_summary": notes[:500],
            "full_output": {"notes": notes, "type": "strategy_directive"},
            "started_at": _dt.datetime.utcnow().isoformat(),
            "finished_at": _dt.datetime.utcnow().isoformat(),
        }
    ).execute()
    return {"noted": True}


def main() -> None:
    ap = argparse.ArgumentParser(description="NemoClaw tools CLI")
    ap.add_argument(
        "--env-file",
        default=os.path.expanduser("~/.openclaw/workspace/.env.nemoclaw"),
        help="Dotenv file with SUPABASE_* and NEXT_PUBLIC_APP_URL",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p_ra = sub.add_parser("read-analytics", help="Query Supabase analytics tables")
    p_ra.add_argument(
        "--type",
        choices=["videos", "channel", "content_queue", "agent_runs", "research"],
        default="channel",
    )
    p_ra.add_argument("--limit", type=int, default=20)
    p_ra.add_argument("--filters", help="JSON object for row filters", default=None)

    p_ta = sub.add_parser("trigger-agent", help="POST /api/run-agent via Next.js")
    p_ta.add_argument(
        "--agent",
        required=True,
        help="strategy | research | content | production | upload | analytics | brainstorm | setup | nemoclaw (use --input for steps JSON)",
    )
    p_ta.add_argument("--input", help="JSON object", default=None)

    p_ap = sub.add_parser("approve-content", help="Approve content_queue row")
    p_ap.add_argument("content_id")

    p_rj = sub.add_parser("reject-content", help="Reject content_queue row")
    p_rj.add_argument("content_id")
    p_rj.add_argument("--reason", default="Did not pass quality checks")

    p_us = sub.add_parser("update-strategy", help="Insert strategy notes for Strategy agent")
    p_us.add_argument("notes")

    args = ap.parse_args()
    load_env_file(args.env_file)

    handlers = {
        "read-analytics": cmd_read_analytics,
        "trigger-agent": cmd_trigger_agent,
        "approve-content": cmd_approve_content,
        "reject-content": cmd_reject_content,
        "update-strategy": cmd_update_strategy,
    }
    out = handlers[args.command](args)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
