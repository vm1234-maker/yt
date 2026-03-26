-- One-shot: wipe app data so agents/dashboard start fresh.
-- Run in Supabase SQL Editor (or via MCP execute_sql). Destructive; no undo.
-- Views niche_performance and pipeline_runs are derived; they reflect empty base tables.

TRUNCATE TABLE public.agent_runs, public.content_queue, public.video_analytics, public.channel_metrics RESTART IDENTITY CASCADE;
