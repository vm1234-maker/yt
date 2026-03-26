from openai import OpenAI
from config import settings
import base64


class OpenAITool:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def generate_text(self, prompt: str, max_tokens: int = 2000, model: str = "gpt-4.1") -> str:
        """Generate text using GPT-4.1."""
        response = self.client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    def generate_image(self, prompt: str, size: str = "1792x1024") -> dict:
        """
        Generate an image using gpt-image-1.
        Returns {"url": str | None, "image_bytes": bytes}.
        size: "1024x1024" | "1792x1024" | "1024x1792"
        """
        response = self.client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size=size,
            n=1,
        )
        item = response.data[0]
        # gpt-image-1 returns b64_json by default
        if hasattr(item, "b64_json") and item.b64_json:
            image_bytes = base64.b64decode(item.b64_json)
            return {"url": None, "image_bytes": image_bytes}
        # fallback: url
        url = item.url or ""
        import httpx
        image_bytes = httpx.get(url, timeout=60).content if url else b""
        return {"url": url, "image_bytes": image_bytes}

    def research(self, query: str) -> str:
        """
        Run a research query using GPT-4.1 with deep knowledge of YouTube trends.
        Falls back gracefully if the model is unavailable.
        """
        response = self.client.chat.completions.create(
            model="gpt-4.1",
            max_tokens=3000,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert YouTube channel analyst with deep knowledge of "
                        "ambient/soundscape content trends, viewer behavior, and monetization. "
                        "Provide accurate, data-informed analysis based on your training knowledge."
                    ),
                },
                {"role": "user", "content": query},
            ],
        )
        return response.choices[0].message.content or ""
