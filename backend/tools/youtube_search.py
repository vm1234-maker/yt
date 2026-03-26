from googleapiclient.discovery import build
from config import settings


class YouTubeSearchTool:
    def __init__(self):
        self.yt = build('youtube', 'v3', developerKey=settings.YOUTUBE_API_KEY)

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        try:
            resp = self.yt.search().list(
                q=query, part='snippet,id', type='video',
                order='viewCount', maxResults=max_results
            ).execute()
            return resp.get('items', [])
        except Exception as e:
            raise RuntimeError(f"YouTubeSearchTool.search failed for '{query}': {e}")

    def video_stats(self, video_ids: list[str]) -> list[dict]:
        try:
            resp = self.yt.videos().list(
                part='statistics,contentDetails',
                id=','.join(video_ids)
            ).execute()
            return resp.get('items', [])
        except Exception as e:
            raise RuntimeError(f"YouTubeSearchTool.video_stats failed: {e}")
