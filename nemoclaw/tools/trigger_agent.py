import httpx
import os


def trigger_agent(agent: str, input: dict = {}) -> dict:
    """
    Trigger an agent run via the Next.js API.
    agent: one of strategy | research | content | production | upload | analytics
    input: optional input data dict
    """
    app_url = os.environ.get("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
    r = httpx.post(
        f"{app_url}/api/run-agent",
        json={"agent": agent, "input": input},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
