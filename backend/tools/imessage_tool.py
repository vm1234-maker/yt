# Requires macOS with Messages.app signed in and Automation permission granted
# to System Events and Messages in System Preferences > Privacy & Security > Automation.
from macpymessenger import Configuration, IMessageClient
from config import settings

def send_imessage(message: str, recipient: str | None = None) -> None:
    """
    Send an iMessage to the configured recipient.
    Requires Messages.app to be signed in and Automation permission granted.
    Only works on macOS.
    """
    to = recipient or settings.IMESSAGE_RECIPIENT
    try:
        client = IMessageClient(Configuration())
        client.send(to, message)
    except Exception as e:
        # Log but don't crash the agent if iMessage fails
        print(f"[iMessage] Failed to send to {to}: {e}")
