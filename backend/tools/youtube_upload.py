import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import settings

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


def get_youtube_client():
    try:
        creds = Credentials(
            token=None,
            refresh_token=settings.YOUTUBE_REFRESH_TOKEN,
            client_id=settings.YOUTUBE_CLIENT_ID,
            client_secret=settings.YOUTUBE_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return build('youtube', 'v3', credentials=creds)
    except Exception as e:
        raise RuntimeError(f"Failed to build YouTube client: {e}")


class YouTubeUploadTool:
    def upload(self, video_path: str, title: str, description: str,
               tags: list[str], scheduled_for: str | None = None) -> str:
        """Upload video, return YouTube video ID."""
        yt = get_youtube_client()

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags[:15],  # YouTube limit
                "categoryId": "10",  # Music
            },
            "status": {
                "privacyStatus": "private" if scheduled_for else "public",
                "publishAt": scheduled_for,
                "selfDeclaredMadeForKids": False,
            },
        }

        # Download from Supabase Storage to local if it's a URL
        local_path = video_path
        if video_path.startswith("http"):
            local_path = f"/tmp/upload_{title[:20].replace(' ', '_')}.mp4"
            try:
                with httpx.stream("GET", video_path, timeout=600, follow_redirects=True) as r:
                    r.raise_for_status()
                    with open(local_path, "wb") as f:
                        for chunk in r.iter_bytes(1024 * 1024):
                            f.write(chunk)
            except Exception as e:
                raise RuntimeError(f"Failed to download video from URL: {e}")

        try:
            media = MediaFileUpload(local_path, chunksize=50 * 1024 * 1024,
                                    resumable=True, mimetype="video/mp4")
            request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

            response = None
            while response is None:
                _, response = request.next_chunk()

            return response["id"]
        except Exception as e:
            raise RuntimeError(f"YouTubeUploadTool.upload failed: {e}")

    def set_thumbnail(self, video_id: str, thumbnail_url: str) -> None:
        try:
            yt = get_youtube_client()
            img_data = httpx.get(thumbnail_url, timeout=30).content
            tmp = f"/tmp/thumb_{video_id}.jpg"
            with open(tmp, "wb") as f:
                f.write(img_data)
            yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(tmp)).execute()
        except Exception as e:
            raise RuntimeError(f"YouTubeUploadTool.set_thumbnail failed for video {video_id}: {e}")
