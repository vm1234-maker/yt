-- Agent run history — every agent writes here after each run
create table if not exists agent_runs (
  id uuid primary key default gen_random_uuid(),
  agent_name text not null,
  status text not null default 'running',   -- 'running' | 'success' | 'error'
  input jsonb,
  output_summary text,
  full_output jsonb,                         -- { log: string[], result: any, progress: number }
  started_at timestamptz default now(),
  finished_at timestamptz,
  duration_ms int
);

create index if not exists agent_runs_agent_name_idx on agent_runs(agent_name);
create index if not exists agent_runs_started_at_idx on agent_runs(started_at desc);

-- Video content queue — one row per video brief
create table if not exists content_queue (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  niche text,
  status text default 'draft',  -- draft | awaiting_approval | approved | in_production | scheduled | uploaded | rejected
  length_hours numeric,
  target_rpm numeric,
  description text,
  tags text[],
  thumbnail_url text,
  audio_url text,
  video_url text,
  youtube_video_id text,
  scheduled_for timestamptz,
  priority text default 'medium',   -- high | medium | low
  created_at timestamptz default now(),
  approved_at timestamptz
);

create index if not exists content_queue_status_idx on content_queue(status);
create index if not exists content_queue_created_at_idx on content_queue(created_at desc);

-- Per-video analytics — written by Analytics Agent every 24h
create table if not exists video_analytics (
  id uuid primary key default gen_random_uuid(),
  youtube_video_id text not null,
  title text,
  recorded_at timestamptz default now(),
  views int default 0,
  watch_time_minutes int default 0,
  rpm numeric default 0,
  ctr numeric default 0,
  avg_view_duration_seconds int default 0,
  estimated_revenue numeric default 0
);

create index if not exists video_analytics_video_id_idx on video_analytics(youtube_video_id);
create index if not exists video_analytics_recorded_at_idx on video_analytics(recorded_at desc);

-- Channel-level weekly rollup
create table if not exists channel_metrics (
  id uuid primary key default gen_random_uuid(),
  recorded_at timestamptz default now(),
  total_views int default 0,
  total_watch_hours numeric default 0,
  subscribers int default 0,
  estimated_revenue numeric default 0,
  avg_rpm numeric default 0,
  avg_ctr numeric default 0,
  period_start date,
  period_end date
);

-- Enable Realtime on the tables the dashboard subscribes to
alter publication supabase_realtime add table agent_runs;
alter publication supabase_realtime add table content_queue;
