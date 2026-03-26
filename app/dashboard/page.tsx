import {
  TrendingUp,
  DollarSign,
  Users,
  PlayCircle,
  ArrowUpRight,
  ArrowRight,
} from 'lucide-react'
import Link from 'next/link'
import { getSupabaseAdmin } from '@/lib/supabase-admin'
import { displaySubscriberCount } from '@/lib/channel-metrics'
import type { AgentRun, ChannelMetrics } from '@/lib/types'
import { ActivityFeed } from '@/components/activity-feed'
import { AgentStatusGrid } from '@/components/agent-status-grid'
import { RunPipelineButton } from '@/components/run-pipeline-button'

function AccentBar({ accent }: { accent: string }) {
  const colors: Record<string, string> = {
    amber: 'var(--amber)',
    green: 'var(--green)',
    blue: 'var(--blue)',
  }
  return (
    <div
      className="absolute left-0 top-3 bottom-3 w-0.5 rounded-full"
      style={{ background: colors[accent] ?? colors.amber }}
    />
  )
}


export default async function DashboardPage() {
  const admin = getSupabaseAdmin()
  if (!admin) {
    return (
      <div className="p-6 space-y-4">
        <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
          Dashboard
        </h1>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Set <code className="mono">NEXT_PUBLIC_SUPABASE_URL</code> and{' '}
          <code className="mono">SUPABASE_SERVICE_ROLE_KEY</code> in{' '}
          <code className="mono">.env.local</code> or Vercel.
        </p>
      </div>
    )
  }

  const [metricsRes, runsRes] = await Promise.all([
    admin
      .from('channel_metrics')
      .select('*')
      .order('recorded_at', { ascending: false })
      .limit(1)
      .maybeSingle(),
    admin
      .from('agent_runs')
      .select('*')
      .order('started_at', { ascending: false })
      .limit(100),
  ])

  const metrics: ChannelMetrics | null = metricsRes.data ?? null
  const runs: AgentRun[] = runsRes.data ?? []

  const runningCount = runs.filter((r) => r.status === 'running').length

  const statsConfig = [
    {
      label: 'Est. Revenue',
      value: metrics ? `$${metrics.estimated_revenue.toFixed(0)}` : '$0',
      change: 'from channel_metrics',
      icon: DollarSign,
      accent: 'green',
    },
    {
      label: 'Watch Hours',
      value: metrics ? metrics.total_watch_hours.toLocaleString() : '0',
      change: 'total watch hours',
      icon: TrendingUp,
      accent: 'blue',
    },
    {
      label: 'Subscribers',
      value: displaySubscriberCount(metrics).toLocaleString(),
      change: 'total or period (channel_metrics)',
      icon: Users,
      accent: 'amber',
    },
    {
      label: 'Total Views',
      value: metrics ? metrics.total_views.toLocaleString() : '0',
      change: 'total channel views',
      icon: PlayCircle,
      accent: 'amber',
    },
  ]

  return (
    <div className="p-6 space-y-6 animate-fade-in-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1
            className="text-2xl font-bold tracking-tight"
            style={{ color: 'var(--text-primary)' }}
          >
            Operations Center
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Ambient channel automation — Phase 1
          </p>
        </div>
        <div className="flex items-center gap-2">
          {runningCount > 0 ? (
            <div
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md mono text-[10px] font-semibold"
              style={{
                background: 'var(--green-glow)',
                border: '1px solid rgba(16,185,129,0.2)',
                color: 'var(--green)',
                letterSpacing: '0.08em',
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 status-dot-green inline-block" />
              {runningCount} AGENT{runningCount !== 1 ? 'S' : ''} RUNNING
            </div>
          ) : (
            <div
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md mono text-[10px] font-semibold"
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                color: 'var(--text-muted)',
                letterSpacing: '0.08em',
              }}
            >
              ALL IDLE
            </div>
          )}
          <div
            className="mono text-[10px]"
            style={{ color: 'var(--text-muted)', letterSpacing: '0.06em' }}
          >
            {new Date().toLocaleDateString('en-US', {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
            })}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        {statsConfig.map((stat) => {
          const Icon = stat.icon
          const accentColors: Record<string, string> = {
            amber: 'var(--amber)',
            green: 'var(--green)',
            blue: 'var(--blue)',
          }
          const accentGlow: Record<string, string> = {
            amber: 'var(--amber-glow)',
            green: 'var(--green-glow)',
            blue: 'var(--blue-glow)',
          }
          const color = accentColors[stat.accent]
          const glow = accentGlow[stat.accent]
          return (
            <div key={stat.label} className="card relative overflow-hidden pl-5">
              <AccentBar accent={stat.accent} />
              <div className="p-4">
                <div className="flex items-start justify-between mb-3">
                  <div
                    className="w-8 h-8 rounded-md flex items-center justify-center"
                    style={{ background: glow, border: `1px solid ${color}30` }}
                  >
                    <Icon size={15} style={{ color }} />
                  </div>
                  <ArrowUpRight size={13} style={{ color: 'var(--text-muted)' }} />
                </div>
                <div
                  className="text-2xl font-bold tracking-tight"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {stat.value}
                </div>
                <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                  {stat.label}
                </div>
                <div className="mono text-[10px] mt-1.5" style={{ color }}>
                  {metrics ? stat.change : 'Waiting for first report'}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Pipeline trigger */}
      <RunPipelineButton />

      {/* Agents + Activity */}
      <div className="grid grid-cols-3 gap-4">
        {/* Agent grid — 2 cols */}
        <div className="col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <p className="section-header">Agent Status</p>
            <Link
              href="/agents"
              className="flex items-center gap-1 mono text-[10px]"
              style={{ color: 'var(--text-muted)' }}
            >
              View all <ArrowRight size={10} />
            </Link>
          </div>
          <AgentStatusGrid initialRuns={runs} />
        </div>

        {/* Activity feed */}
        <div className="space-y-3">
          <p className="section-header">Activity Feed</p>
          <ActivityFeed initial={runs.slice(0, 20)} />
        </div>
      </div>
    </div>
  )
}
