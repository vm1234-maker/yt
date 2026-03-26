# Phase 1 — Supabase Schema + Live Reads

**Goal**: Replace every hardcoded mock array in the four UI pages with real Supabase queries.
No backend needed — Next.js 16 Server Components query Supabase directly using the service role key.

---

## Manual Prerequisites (human does these before subagent runs)

1. Go to supabase.com → create a new project (project ref: hztnoisuhyxdnjgvcaed is already set up)
2. Copy the three keys into `.env.local` (file will be created with placeholders by the subagent)
3. Run the migration SQL in the Supabase SQL editor (SQL provided below)

---

## Package to Install

```bash
npm install @supabase/supabase-js zod
```

`@supabase/supabase-js` — already in package.json from a prior install.
`zod` — needed for Phase 2 API route validation; install now.

---

## Database Migration

File: `supabase/migrations/001_initial.sql`

```sql
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
```

---

## New Files to Create

### `.env.local`

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://hztnoisuhyxdnjgvcaed.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<paste anon key here>
SUPABASE_SERVICE_ROLE_KEY=<paste service role key here>

# Backend (wired in Phase 2)
BACKEND_URL=http://localhost:8000
```

### `lib/types.ts`

TypeScript types for every Supabase table row, used across all pages.

```ts
export type AgentStatus = 'running' | 'success' | 'error' | 'idle'

export interface AgentRun {
  id: string
  agent_name: string
  status: AgentStatus
  input: Record<string, unknown> | null
  output_summary: string | null
  full_output: {
    log?: string[]
    result?: Record<string, unknown>
    progress?: number
  } | null
  started_at: string
  finished_at: string | null
  duration_ms: number | null
}

export type ContentStatus =
  | 'draft'
  | 'awaiting_approval'
  | 'approved'
  | 'in_production'
  | 'scheduled'
  | 'uploaded'
  | 'rejected'

export interface ContentQueueItem {
  id: string
  title: string
  niche: string | null
  status: ContentStatus
  length_hours: number | null
  target_rpm: number | null
  description: string | null
  tags: string[] | null
  thumbnail_url: string | null
  audio_url: string | null
  video_url: string | null
  youtube_video_id: string | null
  scheduled_for: string | null
  priority: 'high' | 'medium' | 'low'
  created_at: string
  approved_at: string | null
}

export interface VideoAnalytics {
  id: string
  youtube_video_id: string
  title: string | null
  recorded_at: string
  views: number
  watch_time_minutes: number
  rpm: number
  ctr: number
  avg_view_duration_seconds: number
  estimated_revenue: number
}

export interface ChannelMetrics {
  id: string
  recorded_at: string
  total_views: number
  total_watch_hours: number
  subscribers: number
  estimated_revenue: number
  avg_rpm: number
  avg_ctr: number
  period_start: string | null
  period_end: string | null
}
```

### `lib/supabase.ts`

```ts
import { createClient } from '@supabase/supabase-js'

// Client-side — anon key, safe to expose, RLS enforced
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

// Server-only — service role, full access, never sent to browser
export const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
)
```

---

## Files to Update

### `app/dashboard/page.tsx`

Becomes `async`. Removes all hardcoded `const stats`, `const agents`, `const activity` arrays.

**Stats cards** — read from latest `channel_metrics` row. If no rows yet, use zero fallbacks.
```ts
const { data: metrics } = await supabaseAdmin
  .from('channel_metrics')
  .select('*')
  .order('recorded_at', { ascending: false })
  .limit(1)
  .single()
// fallback: metrics ?? { total_views: 0, estimated_revenue: 0, total_watch_hours: 0, subscribers: 0 }
```

**Agent grid** — latest run per agent_name from `agent_runs`.
```ts
const { data: runs } = await supabaseAdmin
  .from('agent_runs')
  .select('*')
  .order('started_at', { ascending: false })
  .limit(100)
// Derive one entry per agent_name in JS: group by agent_name, take first of each
```

**Activity feed** — extracted into `components/activity-feed.tsx` (see below). Dashboard passes the initial 20 rows as a prop.

**Running agent count** in the header badge — derived from the runs data (count where status === 'running').

**Empty state** — if tables are empty, every card/section renders a subtle "Waiting for first agent run" placeholder. No blank cards, no JS errors.

### `app/agents/page.tsx`

Becomes `async`. Removes hardcoded `const agents` array.

Fetches all `agent_runs` ordered by `started_at DESC`, limit 500.
Derives per-agent stats in JS:
- `totalRuns` = count of rows for that agent_name
- `successRate` = success rows / total * 100
- `avgDuration` = mean of `duration_ms` where not null, formatted as "Xs" or "Xm Ys"
- `lastRun` = `started_at` of most recent row
- `status` = `status` of most recent row
- `lastLog` = `full_output.log` of most recent row (array of strings)
- `progress` = `full_output.progress` of the running row (if any)

The static `<button>` for "Run" is replaced with `<RunAgentButton agentId={agent.id} />` — a client component created in Phase 2. For now it stays as a visual placeholder button with a TODO comment.

### `app/content/page.tsx`

Becomes `async`. Removes hardcoded `const contentQueue` array.

```ts
const { data: queue } = await supabaseAdmin
  .from('content_queue')
  .select('*')
  .order('created_at', { ascending: false })
```

**Approve / Reject buttons** become a `'use client'` wrapper component `components/content-actions.tsx` that calls Server Actions.

Create `app/content/actions.ts`:
```ts
'use server'
import { supabaseAdmin } from '@/lib/supabase'
import { revalidatePath } from 'next/cache'

export async function approveContent(id: string) {
  await supabaseAdmin
    .from('content_queue')
    .update({ status: 'approved', approved_at: new Date().toISOString() })
    .eq('id', id)
  revalidatePath('/content')
}

export async function rejectContent(id: string) {
  await supabaseAdmin
    .from('content_queue')
    .update({ status: 'rejected' })
    .eq('id', id)
  revalidatePath('/content')
}
```

`components/content-actions.tsx` — `'use client'` component rendering the Approve/Reject buttons, calling these Server Actions via `useTransition`.

The `length` field from the mock data maps to `length_hours` in the DB — format as `${length_hours}h` for display.
The `targetRpm` field maps to `target_rpm` — format as `$${target_rpm.toFixed(2)}` for display.
The `thumbnailReady` flag maps to `thumbnail_url !== null`.
The `audioReady` flag maps to `audio_url !== null`.

### `app/analytics/page.tsx`

Becomes `async`. Removes hardcoded `const topVideos` and `const channelMetrics`.

```ts
const [metricsRes, videosRes] = await Promise.all([
  supabaseAdmin.from('channel_metrics').select('*').order('recorded_at', { ascending: false }).limit(1).single(),
  supabaseAdmin.from('video_analytics').select('*').order('views', { ascending: false }).limit(20)
])
const metrics = metricsRes.data
const videos = videosRes.data ?? []
```

`AnalyticsCharts` component receives `videos` as a prop instead of using hardcoded data. The chart data is derived from `videos` grouped by `recorded_at` date.

Stat cards derive values from `metrics` (with zero fallbacks if null).

---

## New Component: `components/activity-feed.tsx`

`'use client'` component. Gets initial rows as a prop from the dashboard Server Component.
Subscribes to Supabase Realtime INSERT on `agent_runs` so new activity appears live.

```tsx
'use client'
import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import type { AgentRun } from '@/lib/types'

export function ActivityFeed({ initial }: { initial: AgentRun[] }) {
  const [feed, setFeed] = useState(initial)

  useEffect(() => {
    const channel = supabase
      .channel('activity_feed')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'agent_runs' },
        (payload) => setFeed(prev => [payload.new as AgentRun, ...prev].slice(0, 30))
      )
      .subscribe()
    return () => { supabase.removeChannel(channel) }
  }, [])

  // render same activity feed JSX as current dashboard but driven by `feed` state
}
```

---

## Updated: `components/analytics-charts.tsx`

Currently uses hardcoded `viewsData`, `revenueByNiche`, `watchTimeData` arrays.

Add a `data` prop:
```ts
interface AnalyticsChartsProps {
  videos: VideoAnalytics[]
}
```

Derive chart data from `videos` inside the component:
- `viewsData` — group by `recorded_at` date, sum views per day
- `revenueByNiche` — group `content_queue` data by niche (passed as second prop if available, else use video title heuristics)
- `watchTimeData` — group by date, sum `watch_time_minutes / 60`

If `videos` is empty, render a centered "No analytics data yet" message in place of each chart.

---

## Empty State Rules

Every section that reads from Supabase must handle zero rows gracefully:
- Agent cards: show 6 cards with `status: 'idle'`, run count 0, "No runs yet" for last output
- Activity feed: "No activity yet — run an agent to get started"
- Content queue: "No content yet — approve a run from the Agents page"
- Analytics charts: "No analytics data yet" placeholder in chart area
- Stats cards: all values show `0` or `$0`

---

## What Phase 1 Does NOT Include

- No Python backend
- No "Run" button functionality (button exists visually, wired in Phase 2)
- No authentication
- No YouTube API calls
