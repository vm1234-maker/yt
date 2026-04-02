# iMessage only — AppleScript via Messages.app (macOS). No third-party SDK.
# Requires: Messages signed in, IMESSAGE_RECIPIENT set, Automation permission for your terminal/Python.
import subprocess
import sys

from config import settings


def send_imessage(message: str, recipient: str | None = None) -> dict:
    """
    Send an iMessage. Only works on macOS with Messages.app.
    Returns {"sent": True, "recipient": ...} on success; raises on failure.
    """
    if sys.platform != "darwin":
        raise RuntimeError("iMessage requires macOS (Messages.app + osascript).")

    to = (recipient or settings.IMESSAGE_RECIPIENT or "").strip()
    if not to:
        raise ValueError("IMESSAGE_RECIPIENT is not set in backend/.env")

    safe_msg = message.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")

    script = f'''
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "{to}" of targetService
    send "{safe_msg}" to targetBuddy
end tell
'''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "AppleScript failed")

    return {"sent": True, "recipient": to}
