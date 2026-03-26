"""
NemoClaw tool — send an iMessage notification.
Reads IMESSAGE_RECIPIENT from environment.
"""
import os
import subprocess

def send_imessage(message: str, recipient: str | None = None) -> dict:
    """Send an iMessage using AppleScript (fallback if macpymessenger unavailable)."""
    to = recipient or os.environ.get("IMESSAGE_RECIPIENT", "")
    if not to:
        raise ValueError("IMESSAGE_RECIPIENT env var is not set")

    # Escape double quotes in message
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
        raise RuntimeError(f"AppleScript iMessage failed: {result.stderr}")
    return {"sent": True, "recipient": to}
