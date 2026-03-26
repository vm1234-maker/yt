import subprocess
from pathlib import Path

SANDBOX = Path("/sandbox/output")


class FFmpegTool:
    def render(self, audio_path: str, visual_path: str, output_name: str, duration_s: int) -> str:
        """Loop both visual and audio to the target duration, combine into MP4."""
        SANDBOX.mkdir(parents=True, exist_ok=True)
        out = SANDBOX / f"{output_name}.mp4"

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", visual_path,   # loop visual forever
            "-stream_loop", "-1", "-i", audio_path,    # loop audio forever
            "-c:v", "libx264", "-preset", "slow", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration_s),                     # exact target duration controls stop
            "-movflags", "+faststart",
            str(out),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)  # 2hr timeout
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {result.stderr[-1000:]}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("FFmpeg render timed out after 2 hours")

        return str(out)

    def download(self, url: str, dest: str) -> str:
        """Download a file from URL to dest path."""
        import httpx
        SANDBOX.mkdir(parents=True, exist_ok=True)
        try:
            with httpx.stream("GET", url, timeout=300, follow_redirects=True) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=1024 * 1024):
                        f.write(chunk)
        except Exception as e:
            raise RuntimeError(f"FFmpegTool.download failed for {url}: {e}")
        return dest
