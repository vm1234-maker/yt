-- Migration 002: pipeline traceability + analytics completeness
-- Run this in Supabase SQL Editor → New Query → Run

-- ── content_queue additions ─────────────────────────────────────────────────
-- angle: the specific mood/setting angle chosen by the brainstorm (e.g. "deep focus study session")
alter table content_queue add column if not exists angle text;

-- pipeline_run_id: traces which pipeline run produced this content item
alter table content_queue add column if not exists pipeline_run_id uuid;
alter table content_queue add column if not exists brainstorm_run_id uuid;

create index if not exists content_queue_pipeline_run_id_idx on content_queue(pipeline_run_id);

-- ── agent_runs additions ─────────────────────────────────────────────────────
-- pipeline_run_id: links individual step runs (research, brainstorm, content, etc.)
-- back to the parent pipeline run so the dashboard can group them
alter table agent_runs add column if not exists pipeline_run_id uuid;

create index if not exists agent_runs_pipeline_run_id_idx on agent_runs(pipeline_run_id);

-- ── video_analytics additions ────────────────────────────────────────────────
-- impressions: YouTube Analytics API returns this — useful for CTR accuracy
alter table video_analytics add column if not exists impressions int default 0;

-- niche: denormalized from content_queue so analytics queries don't need a join
alter table video_analytics add column if not exists niche text;

-- subscribers_gained: from channel rollup (weekly delta, not total)
alter table video_analytics add column if not exists subscribers_gained int default 0;

-- ── channel_metrics fix ──────────────────────────────────────────────────────
-- 'subscribers' (total) was never written — analytics only gets 'subscribers_gained' (weekly delta)
-- Rename the column to reflect what we actually store
alter table channel_metrics rename column subscribers to subscribers_gained;

-- Add a separate column for total subscribers (populated via YouTube Data API channel stats)
alter table channel_metrics add column if not exists total_subscribers int default 0;

-- ── niche_performance view ───────────────────────────────────────────────────
-- Materialized view so Strategy Agent can read pre-aggregated niche stats in one query
-- instead of joining video_analytics + content_queue every time
create or replace view niche_performance as
select
  cq.niche,
  count(distinct cq.id)                                         as total_uploads,
  round(avg(va.rpm)::numeric, 2)                                as avg_rpm,
  round(avg(va.views)::numeric, 0)                              as avg_views,
  round(avg(va.estimated_revenue)::numeric, 2)                  as avg_revenue,
  round(
    avg(
      case when cq.length_hours > 0
        then va.avg_view_duration_seconds::numeric / (cq.length_hours * 3600)
        else null
      end
    )::numeric, 3
  )                                                             as avg_retention,
  round(avg(va.ctr)::numeric, 4)                                as avg_ctr,
  max(va.recorded_at)                                           as last_updated
from content_queue cq
join video_analytics va on va.youtube_video_id = cq.youtube_video_id
where cq.youtube_video_id is not null
group by cq.niche;

-- ── pipeline_runs view ───────────────────────────────────────────────────────
-- Convenience view: show pipeline runs with their key child runs grouped
create or replace view pipeline_runs as
select
  p.id                                              as pipeline_run_id,
  p.status                                          as pipeline_status,
  p.started_at,
  p.finished_at,
  p.duration_ms,
  p.output_summary,
  (p.full_output->>'step')                          as current_step,
  (p.full_output->>'content_id')::uuid              as content_id,
  (p.full_output->>'youtube_video_id')              as youtube_video_id,
  (p.full_output->>'discussion_turns')::int         as discussion_turns
from agent_runs p
where p.agent_name = 'pipeline'
order by p.started_at desc;
