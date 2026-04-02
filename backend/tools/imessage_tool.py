# iMessage only — AppleScript via Messages.app (macOS). No third-party SDK.
# Requires: Messages signed in, IMESSAGE_RECIPIENT set, Automation permission for your terminal/Python.
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from config import settings

# First run often waits on the macOS "Allow control of Messages" dialog — needs a long timeout.
_OSA_TIMEOUT_SEC = 120


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

    fd, raw_path = tempfile.mkstemp(suffix=".txt", prefix="imessage_")
    path = Path(raw_path).resolve()
    try:
        os.write(fd, message.encode("utf-8"))
    finally:
        os.close(fd)

    # Load body via shell so UTF-8 and newlines are safe; avoid embedding text in AppleScript literals.
    p = str(path).replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "Messages" to activate
delay 0.5
set posixPath to "{p}"
set msg to do shell script "cat " & quoted form of posixPath
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "{to}" of targetService
    send msg to targetBuddy
end tell
'''
    try:
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=_OSA_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "AppleScript timed out (often the macOS permission dialog is waiting). "
                "Click Allow so Terminal or your IDE can control Messages, then run again. "
                "Or run from Terminal.app: cd backend && .venv/bin/python scripts/test_imessage.py. "
                "Ensure the number matches an existing iMessage conversation in Messages."
            ) from exc
        if result.returncode != 0:
            err = (result.stderr or "").strip()
            raise RuntimeError(
                err
                or "AppleScript failed (check Messages is signed in and IMESSAGE_RECIPIENT matches a buddy)."
            )

        return {"sent": True, "recipient": to}
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
