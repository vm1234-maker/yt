from supabase import create_client
import os
import datetime
from send_imessage import send_imessage


def _db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def approve_content(content_id: str) -> dict:
    """Approve a content_queue item."""
    db = _db()
    db.table("content_queue").update({
        "status": "approved",
        "approved_at": datetime.datetime.utcnow().isoformat(),
    }).eq("id", content_id).execute()
    send_imessage(f"✅ Content {content_id[:8]} auto-approved by NemoClaw.\n\nApprove/reject at: http://localhost:3000/content")
    return {"approved": True, "content_id": content_id}


def reject_content(content_id: str, reason: str = "Did not pass quality checks") -> dict:
    """Reject a content_queue item."""
    db = _db()
    db.table("content_queue").update({"status": "rejected"}).eq("id", content_id).execute()
    send_imessage(f"❌ Content {content_id[:8]} rejected.\nReason: {reason}\n\nApprove/reject at: http://localhost:3000/content")
    return {"rejected": True, "content_id": content_id}
