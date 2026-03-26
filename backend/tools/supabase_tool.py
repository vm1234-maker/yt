from supabase import create_client
from config import settings
from typing import Any


class SupabaseTool:
    def __init__(self):
        self.db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    def select(self, table: str, filters: dict = {}, limit: int = 100) -> list[dict]:
        query = self.db.table(table).select("*")
        for key, val in filters.items():
            query = query.eq(key, val)
        return query.limit(limit).execute().data or []

    def insert(self, table: str, data: dict) -> dict:
        result = self.db.table(table).insert(data).execute()
        return result.data[0] if result.data else {}

    def update(self, table: str, data: dict, match: dict) -> None:
        query = self.db.table(table).update(data)
        for key, val in match.items():
            query = query.eq(key, val)
        query.execute()

    def update_run_log(self, run_id: str, log_lines: list[str], progress: int | None = None) -> None:
        """Append log lines to an agent_run's full_output during execution."""
        current = self.db.table("agent_runs").select("full_output").eq("id", run_id).single().execute()
        existing = current.data.get("full_output") or {}
        existing_log = existing.get("log", [])
        update_data: dict[str, Any] = {"full_output": {**existing, "log": existing_log + log_lines}}
        if progress is not None:
            update_data["full_output"]["progress"] = progress
        self.db.table("agent_runs").update(update_data).eq("id", run_id).execute()

    def log_agent_run(self, run_id: str, agent_name: str, input_data: dict, pipeline_run_id: str | None = None) -> dict:
        """Insert a new agent_run row with status 'running'."""
        import datetime
        row: dict = {
            "id": run_id,
            "agent_name": agent_name,
            "status": "running",
            "input": input_data,
            "started_at": datetime.datetime.utcnow().isoformat(),
            "full_output": {"log": [], "progress": 0},
        }
        if pipeline_run_id:
            row["pipeline_run_id"] = pipeline_run_id
        return self.insert("agent_runs", row)

    def complete_agent_run(self, run_id: str, result: dict) -> None:
        """Mark an agent_run as success and store its output."""
        import datetime, time
        self.update("agent_runs", {
            "status": "success",
            "output_summary": result.get("summary", "")[:500],
            "full_output": result,
            "finished_at": datetime.datetime.utcnow().isoformat(),
        }, {"id": run_id})

    def fail_agent_run(self, run_id: str, error: str) -> None:
        """Mark an agent_run as error."""
        import datetime
        self.update("agent_runs", {
            "status": "error",
            "output_summary": error[:500],
            "finished_at": datetime.datetime.utcnow().isoformat(),
        }, {"id": run_id})
