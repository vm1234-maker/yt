from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase (required)
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # Redis / Celery (required)
    UPSTASH_REDIS_REST_URL: str
    UPSTASH_REDIS_REST_TOKEN: str

    # AI APIs (filled in Phase 3)
    OPENAI_API_KEY: str = ""

    # YouTube (filled in Phase 3)
    YOUTUBE_API_KEY: str = ""
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REFRESH_TOKEN: str = ""

    # NemoClaw / iMessage — daily digest uses AppleScript; Beat must run on macOS (see plans/AUTONOMOUS-OPERATIONS.md)
    IMESSAGE_RECIPIENT: str = ""

    # Autonomous operation (see plans/AUTONOMOUS-OPERATIONS.md)
    # Weekly Strategy Agent triggers Content via Next.js API — enable only when you want hands-off ideation.
    AUTO_STRATEGY_WEEKLY: bool = False
    # Skip dashboard approval after Content step in run-pipeline (Production → Upload run without you)
    AUTO_APPROVE_AFTER_CONTENT: bool = False
    # Full pipeline on a Beat schedule — high impact; off by default (see plans/AUTONOMY-IMPLEMENTATION.md)
    AUTO_PIPELINE_WEEKLY: bool = False


settings = Settings()
