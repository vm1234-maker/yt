import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config import settings

SCOPES = ["https://www.googleapis.com/auth/yt-analytics.readonly"]


def get_analytics_client():
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
        return build('youtubeAnalytics', 'v2', credentials=creds)
    except Exception as e:
        raise RuntimeError(f"Failed to build YouTube Analytics client: {e}")


class YouTubeAnalyticsTool:
    def get_video_metrics(self, video_id: str) -> dict:
        try:
            yt = get_analytics_client()
            end = datetime.date.today().isoformat()
            start = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

            r = yt.reports().query(
                ids="channel==MINE",
                startDate=start,
                endDate=end,
                metrics="views,estimatedMinutesWatched,estimatedRevenue,annotationClickThroughRate,averageViewDuration",
                dimensions="video",
                filters=f"video=={video_id}",
            ).execute()

            rows = r.get("rows", [])
            if not rows:
                return {}
            row = rows[0]
            return {
                "views": int(row[1]),
                "watch_time_minutes": int(row[2]),
                "estimated_revenue": float(row[3]),
                "ctr": float(row[4]),
                "avg_view_duration_seconds": int(row[5]),
            }
        except Exception as e:
            raise RuntimeError(f"YouTubeAnalyticsTool.get_video_metrics failed for {video_id}: {e}")

    def get_channel_rollup(self) -> dict:
        try:
            yt = get_analytics_client()
            end = datetime.date.today().isoformat()
            start = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

            r = yt.reports().query(
                ids="channel==MINE",
                startDate=start,
                endDate=end,
                metrics="views,estimatedMinutesWatched,estimatedRevenue,subscribersGained,annotationClickThroughRate",
            ).execute()

            row = r.get("rows", [[0, 0, 0, 0, 0]])[0]
            return {
                "total_views": int(row[0]),
                "total_watch_hours": round(int(row[1]) / 60, 1),
                "estimated_revenue": float(row[2]),
                "subscribers_gained": int(row[3]),
                "avg_ctr": float(row[4]),
                "period_start": start,
                "period_end": end,
            }
        except Exception as e:
            raise RuntimeError(f"YouTubeAnalyticsTool.get_channel_rollup failed: {e}")
