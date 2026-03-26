# Phase 4 — Real-time Dashboard Wiring

**Goal**: Every status change an agent makes in Supabase appears in the dashboard immediately.
No page refresh needed. Builds on the Realtime infrastructure from Phase 1.

**Depends on**: Phase 2 complete (agents write to Supabase, run-agent button works)

---

## What Gets Live-Updated and How

| UI Element | Component | Mechanism | Interval |
|---|---|---|---|
| Agent dots in sidebar nav | `components/nav.tsx` | Realtime `*` on `agent_runs` | Push |
| Agent status cards on dashboard | `components/agent-status-grid.tsx` | Realtime `*` on `agent_runs` | Push |
| Activity feed | `components/activity-feed.tsx` | Realtime INSERT (already Phase 1) | Push |
| Progress bar on running agent | `components/live-agent-card.tsx` | Poll `/api/agent-status/{id}` | 5s |
| Log terminal on `/agents` | `components/live-agent-card.tsx` | Realtime UPDATE on specific run | Push |
| Content queue status changes | `components/content-queue-table.tsx` | Realtime UPDATE on `content_queue` | Push |
| Stats cards | `app/dashboard/page.tsx` | Server Component + `revalidatePath` | On agent success |

---

## New Files to Create

```
components/
  agent-status-grid.tsx       # extracted from dashboard, Realtime subscribed
  live-agent-card.tsx         # single agent card with live log + progress polling
  content-queue-table.tsx     # extracted from content page, Realtime subscribed
```

---

## Files to Update

```
components/nav.tsx              # sidebar dots become live
app/dashboard/page.tsx          # passes initial data to AgentStatusGrid
app/agents/page.tsx             # wraps cards in LiveAgentCard
app/content/page.tsx            # wraps table in ContentQueueTable
```

---

## `components/agent-status-grid.tsx`

Extracted from `app/dashboard/page.tsx`. Receives initial runs as props. Subscribes to Realtime.

```tsx
'use client'
import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import type { AgentRun } from '@/lib/types'
import { Cpu, Clock, Loader2, Minus, AlertCircle } from 'lucide-react'

interface Props {
  initialRuns: AgentRun[]
}

const AGENT_META: Record<string, { name: string; role: string }> = {
  strategy:   { name: 'Strategy Agent',   role: 'Content Strategist & ROI Optimizer' },
  research:   { name: 'Research Agent',   role: 'YouTube Trend Analyst' },
  content:    { name: 'Content Agent',    role: 'Title, Thumbnail & Metadata Creator' },
  production: { name: 'Production Agent', role: 'Audio Generation & FFmpeg Renderer' },
  upload:     { name: 'Upload Agent',     role: 'YouTube Data API v3 Publisher' },
  analytics:  { name: 'Analytics Agent',  role: 'Performance Monitor & Reporter' },
}

export function AgentStatusGrid({ initialRuns }: Props) {
  // Keep latest run per agent_name
  const [runMap, setRunMap] = useState<Record<string, AgentRun>>(() => {
    const map: Record<string, AgentRun> = {}
    for (const run of initialRuns) {
      if (!map[run.agent_name] || run.started_at > map[run.agent_name].started_at) {
        map[run.agent_name] = run
      }
    }
    return map
  })

  useEffect(() => {
    const channel = supabase
      .channel('agent_status_grid')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'agent_runs' },
        (payload) => {
          const updated = payload.new as AgentRun
          setRunMap(prev => {
            const existing = prev[updated.agent_name]
            if (!existing || updated.started_at >= existing.started_at) {
              return { ...prev, [updated.agent_name]: updated }
            }
            return prev
          })
        }
      )
      .subscribe()
    return () => { supabase.removeChannel(channel) }
  }, [])

  return (
    <div className="grid grid-cols-2 gap-3">
      {Object.entries(AGENT_META).map(([agentId, meta]) => {
        const run = runMap[agentId]
        const status = run?.status ?? 'idle'
        const progress = run?.full_output?.progress
        const lastOutput = run?.output_summary ?? 'No runs yet'
        const runCount = 0 // derives from all runs — passed separately if needed
        const lastRun = run ? new Date(run.started_at).toLocaleTimeString() : '—'

        return (
          <div key={agentId} className="card p-4 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <Cpu size={13} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
                <span className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                  {meta.name}
                </span>
              </div>
              <span className={`badge ${status === 'running' ? 'badge-running' : status === 'error' ? 'badge-error' : 'badge-idle'}`}>
                {status}
              </span>
            </div>
            <p className="text-[11px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {lastOutput}
            </p>
            {status === 'running' && typeof progress === 'number' && (
              <div className="space-y-1">
                <div className="progress-bar-track">
                  <div className="progress-bar-fill progress-bar-fill-green" style={{ width: `${progress}%` }} />
                </div>
                <div className="mono text-[10px] text-right" style={{ color: 'var(--green)' }}>{progress}%</div>
              </div>
            )}
            <div className="flex items-center justify-between pt-1" style={{ borderTop: '1px solid var(--border)' }}>
              <div className="flex items-center gap-1">
                <Clock size={10} style={{ color: 'var(--text-muted)' }} />
                <span className="mono text-[10px]" style={{ color: 'var(--text-muted)' }}>{lastRun}</span>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
```

---

## `components/live-agent-card.tsx`

Used on the `/agents` page. Handles both Realtime log streaming and progress polling.

```tsx
'use client'
import { useEffect, useState, useRef } from 'react'
import { supabase } from '@/lib/supabase'
import type { AgentRun } from '@/lib/types'
import { RunAgentButton } from './run-agent-button'
import { Cpu, SquareTerminal, Loader2 } from 'lucide-react'

interface Props {
  agentId: string
  agentName: string
  agentRole: string
  initialRun: AgentRun | null
  inputs: string[]
  outputs: string[]
  totalRuns: number
  successRate: number
  avgDuration: string
}

export function LiveAgentCard({
  agentId, agentName, agentRole, initialRun,
  inputs, outputs, totalRuns, successRate, avgDuration
}: Props) {
  const [run, setRun] = useState<AgentRun | null>(initialRun)
  const logRef = useRef<HTMLDivElement>(null)

  // Realtime subscription for log updates
  useEffect(() => {
    if (!run?.id) return
    const channel = supabase
      .channel(`run_${run.id}`)
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'agent_runs', filter: `id=eq.${run.id}` },
        (payload) => setRun(payload.new as AgentRun)
      )
      .subscribe()
    return () => { supabase.removeChannel(channel) }
  }, [run?.id])

  // Poll for progress when running (fallback if Realtime misses updates)
  useEffect(() => {
    if (run?.status !== 'running') return
    const interval = setInterval(async () => {
      const res = await fetch(`/api/agent-status/${run.id}`)
      if (!res.ok) return
      const updated: AgentRun = await res.json()
      setRun(updated)
      if (updated.status !== 'running') clearInterval(interval)
    }, 5000)
    return () => clearInterval(interval)
  }, [run?.status, run?.id])

  // Auto-scroll log terminal
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [run?.full_output?.log])

  const status = run?.status ?? 'idle'
  const logs = run?.full_output?.log ?? []
  const progress = run?.full_output?.progress

  return (
    <div className="card flex flex-col">
      {/* header */}
      <div className="p-4 flex items-start justify-between gap-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-start gap-3 min-w-0">
          <div className="w-9 h-9 rounded-md flex items-center justify-center flex-shrink-0"
            style={{ background: status === 'running' ? 'var(--green-glow)' : 'var(--bg-elevated)',
                     border: `1px solid ${status === 'running' ? 'rgba(16,185,129,0.2)' : 'var(--border)'}` }}>
            {status === 'running'
              ? <Loader2 size={15} className="animate-spin" style={{ color: 'var(--green)' }} />
              : <Cpu size={15} style={{ color: 'var(--text-secondary)' }} />}
          </div>
          <div>
            <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{agentName}</span>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>{agentRole}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`badge ${status === 'running' ? 'badge-running' : status === 'error' ? 'badge-error' : 'badge-idle'}`}>
            {status}
          </span>
          <RunAgentButton agentId={agentId} onTriggered={(runId) => {
            // Immediately show running state while we wait for Realtime
            setRun(prev => prev ? { ...prev, id: runId, status: 'running' } : {
              id: runId, agent_name: agentId, status: 'running',
              input: null, output_summary: null, full_output: null,
              started_at: new Date().toISOString(), finished_at: null, duration_ms: null
            })
          }} />
        </div>
      </div>

      {/* metrics */}
      <div className="grid grid-cols-4 divide-x" style={{ borderBottom: '1px solid var(--border)', borderColor: 'var(--border)' }}>
        {[
          { label: 'RUNS', value: totalRuns },
          { label: 'SUCCESS', value: `${successRate}%` },
          { label: 'AVG TIME', value: avgDuration },
          { label: 'LAST RUN', value: run ? new Date(run.started_at).toLocaleTimeString() : '—' },
        ].map(m => (
          <div key={m.label} className="px-3 py-2 text-center" style={{ borderColor: 'var(--border)' }}>
            <div className="mono text-[9px] font-semibold" style={{ color: 'var(--text-muted)', letterSpacing: '0.08em' }}>{m.label}</div>
            <div className="text-xs font-bold mt-0.5" style={{ color: 'var(--text-primary)' }}>{m.value}</div>
          </div>
        ))}
      </div>

      {/* progress bar */}
      {status === 'running' && typeof progress === 'number' && (
        <div className="px-4 py-2" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="flex items-center justify-between mb-1">
            <span className="mono text-[10px]" style={{ color: 'var(--text-muted)' }}>Progress</span>
            <span className="mono text-[10px]" style={{ color: 'var(--green)' }}>{progress}%</span>
          </div>
          <div className="progress-bar-track">
            <div className="progress-bar-fill progress-bar-fill-green" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      {/* I/O chips */}
      <div className="px-4 py-3 grid grid-cols-2 gap-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <div>
          <p className="mono text-[9px] font-semibold mb-1.5" style={{ color: 'var(--text-muted)', letterSpacing: '0.08em' }}>INPUTS</p>
          <div className="flex flex-wrap gap-1">
            {inputs.map(i => (
              <span key={i} className="mono text-[10px] px-1.5 py-0.5 rounded"
                style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>{i}</span>
            ))}
          </div>
        </div>
        <div>
          <p className="mono text-[9px] font-semibold mb-1.5" style={{ color: 'var(--text-muted)', letterSpacing: '0.08em' }}>OUTPUTS</p>
          <div className="flex flex-wrap gap-1">
            {outputs.map(o => (
              <span key={o} className="mono text-[10px] px-1.5 py-0.5 rounded"
                style={{ background: 'var(--amber-glow)', border: '1px solid rgba(245,158,11,0.15)', color: 'var(--amber)' }}>{o}</span>
            ))}
          </div>
        </div>
      </div>

      {/* log terminal */}
      <div className="p-4">
        <div className="flex items-center gap-1.5 mb-2">
          <SquareTerminal size={11} style={{ color: 'var(--text-muted)' }} />
          <span className="mono text-[9px]" style={{ color: 'var(--text-muted)', letterSpacing: '0.08em' }}>
            {status === 'running' ? 'LIVE LOG' : 'LAST RUN LOG'}
          </span>
        </div>
        <div className="log-terminal" ref={logRef}>
          {logs.length === 0 && (
            <span style={{ color: 'var(--text-muted)' }}>No runs yet</span>
          )}
          {logs.map((line, i) => {
            const isWarn = line.includes('WARN')
            const isError = line.includes('ERROR')
            const tsEnd = line.indexOf(']') + 1
            return (
              <div key={i} className={isWarn ? 'log-warn' : isError ? 'log-error' : ''}>
                <span className="log-timestamp">{line.slice(0, tsEnd)}</span>
                {line.slice(tsEnd)}
              </div>
            )
          })}
          {status === 'running' && <span className="cursor-blink" style={{ color: 'var(--green)' }}>█</span>}
        </div>
      </div>
    </div>
  )
}
```

---

## `components/content-queue-table.tsx`

Extracted from `app/content/page.tsx`. Realtime on `content_queue` UPDATE.

```tsx
'use client'
import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import type { ContentQueueItem } from '@/lib/types'
import { ContentActions } from './content-actions'

interface Props { initialQueue: ContentQueueItem[] }

export function ContentQueueTable({ initialQueue }: Props) {
  const [queue, setQueue] = useState(initialQueue)

  useEffect(() => {
    const channel = supabase
      .channel('content_queue_live')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'content_queue' },
        (payload) => {
          if (payload.eventType === 'INSERT') {
            setQueue(prev => [payload.new as ContentQueueItem, ...prev])
          } else if (payload.eventType === 'UPDATE') {
            setQueue(prev => prev.map(item =>
              item.id === (payload.new as ContentQueueItem).id
                ? payload.new as ContentQueueItem
                : item
            ))
          } else if (payload.eventType === 'DELETE') {
            setQueue(prev => prev.filter(item => item.id !== (payload.old as ContentQueueItem).id))
          }
        }
      )
      .subscribe()
    return () => { supabase.removeChannel(channel) }
  }, [])

  // renders same table JSX as content page but driven by live queue state
  // ContentActions handles approve/reject Server Actions
}
```

---

## Update `components/nav.tsx`

The hardcoded `agentStatuses` array is replaced with a Realtime subscription.

The nav fetches the latest run per agent on mount, then subscribes to `agent_runs` for live updates.

```tsx
// Inside Nav component:
const [agentDots, setAgentDots] = useState<Record<string, string>>({
  strategy: 'idle', research: 'idle', content: 'idle',
  production: 'idle', upload: 'idle', analytics: 'idle',
})

useEffect(() => {
  // Initial fetch
  fetch('/api/agents')
    .then(r => r.json())
    .then((agents: any[]) => {
      const dots: Record<string, string> = {}
      for (const a of agents) dots[a.agent_id] = a.status
      setAgentDots(dots)
    })

  // Realtime updates
  const channel = supabase
    .channel('nav_agent_dots')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'agent_runs' },
      (payload) => {
        const run = payload.new as any
        setAgentDots(prev => ({ ...prev, [run.agent_name]: run.status }))
      })
    .subscribe()
  return () => { supabase.removeChannel(channel) }
}, [])
```

---

## Update `app/dashboard/page.tsx`

Pass initial runs to `<AgentStatusGrid>` and `<ActivityFeed>` as props.
The page remains a Server Component for SSR of initial data.

```tsx
// In the page:
const { data: runs } = await supabaseAdmin
  .from('agent_runs')
  .select('*')
  .order('started_at', { ascending: false })
  .limit(100)

// Pass to client components:
<AgentStatusGrid initialRuns={runs ?? []} />
<ActivityFeed initial={(runs ?? []).slice(0, 20)} />
```

---

## Update `app/agents/page.tsx`

Replace agent cards with `<LiveAgentCard>` components.
All per-agent stats (run count, success rate, avg duration) are computed server-side from the initial runs data,
then passed as props. The `LiveAgentCard` handles all live updates from Realtime + polling.

---

## `revalidatePath` After Agent Writes

When a Celery task finishes successfully and writes to Supabase, the stats cards on the dashboard
need refreshed server-side data on the next request. This is handled via:

- `revalidatePath('/dashboard')` called from content approve/reject Server Actions
- Stats cards use `{ next: { revalidate: 300 } }` (5-minute ISR) for the channel_metrics query
- This means stats are at most 5 minutes stale, while all agent activity is live via Realtime

---

## What Phase 4 Does NOT Include

- No changes to the Python backend
- No new Supabase tables or schema changes
- Analytics charts still use hardcoded data structure (populated by Analytics Agent in Phase 3)
