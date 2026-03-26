from supabase import create_client
from config import settings


class SupabaseStorageTool:
    def __init__(self):
        self.db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    def upload_file(self, local_path: str, bucket: str, storage_path: str) -> str:
        """Upload file to Supabase Storage, return public URL."""
        try:
            with open(local_path, "rb") as f:
                data = f.read()

            mime = "video/mp4" if local_path.endswith(".mp4") else "image/jpeg"
            self.db.storage.from_(bucket).upload(
                path=storage_path,
                file=data,
                file_options={"content-type": mime, "upsert": "true"}
            )
            return self.db.storage.from_(bucket).get_public_url(storage_path)
        except Exception as e:
            raise RuntimeError(f"SupabaseStorageTool.upload_file failed for '{local_path}': {e}")
