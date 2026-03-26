"""
Run once to generate YOUTUBE_REFRESH_TOKEN.
Usage: python3 tools/youtube_auth.py   (from backend/)
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

flow = InstalledAppFlow.from_client_config(
    {
        "web": {
            "client_id": input("Enter YOUTUBE_CLIENT_ID: ").strip(),
            "client_secret": input("Enter YOUTUBE_CLIENT_SECRET: ").strip(),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:9000/"],
        }
    },
    scopes=SCOPES,
)
# Port 9000 — add http://localhost:9000/ to OAuth client "Authorized redirect URIs"
# access_type + prompt help Google return a refresh_token (not just None)
creds = flow.run_local_server(
    port=9000,
    access_type="offline",
    prompt="consent",
)
if not creds.refresh_token:
    raise SystemExit(
        "No refresh_token returned. Open https://myaccount.google.com/permissions "
        "→ remove access for this app → run this script again."
    )
print(f"\nYOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
