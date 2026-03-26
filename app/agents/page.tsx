import { getSupabaseAdmin } from '@/lib/supabase-admin'
import type { AgentRun } from '@/lib/types'
import { LiveAgentCard } from '@/components/live-agent-card'
import { SetupAgentButton } from '@/components/setup-agent-button'

export const dynamic = 'force-dynamic'

const AGENT_META: Record<string, { name: string; role: string; inputs: string[]; outputs: string[] }> = {
  pipeline:   { name: 'Full Pipeline',    role: 'Research → Brainstorm → Content → [approval] → Production → Upload', inputs: ['optional_input'], outputs: ['content_queue', 'youtube_video_id'] },
  strategy:   { name: 'Strategy Agent',   role: 'Content Strategist & ROI Optimizer',    inputs: ['analytics_report', 'research_report'], outputs: ['content_plan', 'niche_priority'] },
  research:   { name: 'Research Agent',   role: 'YouTube Trend Analyst',                 inputs: ['niche_list', 'youtube_api'], outputs: ['niche_report', 'rpm_estimates'] },
  content:    { name: 'Content Agent',    role: 'Title, Thumbnail & Metadata Creator',   inputs: ['niche', 'angle', 'length_hours'],      outputs: ['title', 'description', 'tags', 'thumbnail'] },
  production: { name: 'Production Agent', role: 'CC0 Loop Assembly & FFmpeg Renderer',   inputs: ['content_id'],                          outputs: ['mp4_file', 'video_url'] },
  upload:     { name: 'Upload Agent',     role: 'YouTube Data API v3 Publisher',         inputs: ['content_id', 'video_url'],             outputs: ['youtube_video_id'] },
  analytics:  { name: 'Analytics Agent',  role: 'Performance Monitor & Reporter',        inputs: ['youtube_analytics_api'],               outputs: ['video_analytics', 'channel_metrics'] },
}

function formatDuration(ms: number): string {
  if (ms < 60000) return `${Math.round(ms / 1000)}s`
  const m = Math.floor(ms / 60000)
  const s = Math.round((ms % 60000) / 1000)
  return `${m}m ${s}s`
}

function buildAgentStats(allRuns: AgentRun[], agentId: string) {
  const agentRuns = allRuns.filter(r => r.agent_name === agentId)
  const totalRuns = agentRuns.length

  if (totalRuns === 0) {
    return { totalRuns: 0, successRate: 0, avgDuration: '—', mostRecent: null as AgentRun | null }
  }

  const successCount = agentRuns.filter(r => r.status === 'success').length
  const successRate = Math.round((successCount / totalRuns) * 100 * 10) / 10

  const durationsMs = agentRuns.map(r => r.duration_ms).filter((d): d is number => d !== null)
  const avgMs = durationsMs.length > 0
    ? durationsMs.reduce((a, b) => a + b, 0) / durationsMs.length
    : null
  const avgDuration = avgMs !== null ? formatDuration(avgMs) : '—'

  const mostRecent = agentRuns[0]

  return { totalRuns, successRate, avgDuration, mostRecent }
}

export default async function AgentsPage() {
  const admin = getSupabaseAdmin()
  if (!admin) {
    return (
      <div className="p-6 space-y-4">
        <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
          Agents
        </h1>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Set <code className="mono">NEXT_PUBLIC_SUPABASE_URL</code> and{' '}
          <code className="mono">SUPABASE_SERVICE_ROLE_KEY</code> in{' '}
          <code className="mono">.env.local</code> or Vercel.
        </p>
      </div>
    )
  }

  const { data: allRuns } = await admin
    .from('agent_runs')
    .select('*')
    .order('started_at', { ascending: false })
    .limit(500)

  const runs: AgentRun[] = allRuns ?? []

  return (
    <div className="p-6 space-y-6 animate-fade-in-up">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
            Agent Management
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            7 agents + full pipeline — monitor status, inspect logs, trigger runs
          </p>
        </div>
        <SetupAgentButton />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {Object.entries(AGENT_META).map(([agentId, meta]) => {
          const stats = buildAgentStats(runs, agentId)
          return (
            <LiveAgentCard
              key={agentId}
              agentId={agentId}
              agentName={meta.name}
              agentRole={meta.role}
              initialRun={stats.mostRecent}
              inputs={meta.inputs}
              outputs={meta.outputs}
              totalRuns={stats.totalRuns}
              successRate={stats.successRate}
              avgDuration={stats.avgDuration}
            />
          )
        })}
      </div>
    </div>
  )
}
