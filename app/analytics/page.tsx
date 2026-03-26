import AnalyticsCharts from '@/components/analytics-charts'
import { TrendingUp, Eye, Clock, DollarSign, MousePointerClick, Users } from 'lucide-react'
import { supabaseAdmin } from '@/lib/supabase-admin'
import { displaySubscriberCount } from '@/lib/channel-metrics'
import type { VideoAnalytics, ChannelMetrics } from '@/lib/types'

export default async function AnalyticsPage() {
  const [metricsRes, videosRes] = await Promise.all([
    supabaseAdmin
      .from('channel_metrics')
      .select('*')
      .order('recorded_at', { ascending: false })
      .limit(1)
      .single(),
    supabaseAdmin
      .from('video_analytics')
      .select('*')
      .order('views', { ascending: false })
      .limit(20),
  ])

  const metrics: ChannelMetrics | null = metricsRes.data ?? null
  const videos: VideoAnalytics[] = videosRes.data ?? []

  const channelMetrics = [
    {
      label: 'Total Views',
      value: metrics ? metrics.total_views.toLocaleString() : '0',
      icon: Eye,
      color: 'var(--blue)',
      change: metrics ? 'from channel_metrics' : 'Waiting for first report',
    },
    {
      label: 'Watch Hours',
      value: metrics ? metrics.total_watch_hours.toLocaleString() : '0',
      icon: Clock,
      color: 'var(--green)',
      change: metrics ? 'total watch hours' : 'Waiting for first report',
    },
    {
      label: 'Avg RPM',
      value: metrics ? `$${metrics.avg_rpm.toFixed(2)}` : '$0.00',
      icon: DollarSign,
      color: 'var(--amber)',
      change: metrics ? 'channel average RPM' : 'Waiting for first report',
    },
    {
      label: 'Avg CTR',
      value: metrics ? `${metrics.avg_ctr.toFixed(1)}%` : '0%',
      icon: MousePointerClick,
      color: 'var(--blue)',
      change: metrics ? 'channel average CTR' : 'Waiting for first report',
    },
    {
      label: 'Subscribers',
      value: metrics ? displaySubscriberCount(metrics).toLocaleString() : '0',
      icon: Users,
      color: 'var(--green)',
      change: metrics ? 'channel subscribers' : 'Waiting for first report',
    },
    {
      label: 'Est. Revenue',
      value: metrics ? `$${metrics.estimated_revenue.toFixed(0)}` : '$0',
      icon: TrendingUp,
      color: 'var(--amber)',
      change: metrics ? 'estimated channel revenue' : 'Waiting for first report',
    },
  ]

  return (
    <div className="p-6 space-y-6 animate-fade-in-up">
      <div>
        <h1
          className="text-2xl font-bold tracking-tight"
          style={{ color: 'var(--text-primary)' }}
        >
          Channel Analytics
        </h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
          Performance data — last 30 days
        </p>
      </div>

      {/* Metric grid */}
      <div className="grid grid-cols-3 gap-3">
        {channelMetrics.map((m) => {
          const Icon = m.icon
          return (
            <div key={m.label} className="card p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {m.label}
                </span>
                <Icon size={13} style={{ color: m.color }} />
              </div>
              <div className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {m.value}
              </div>
              <div className="mono text-[10px] mt-1" style={{ color: m.color }}>
                {m.change}
              </div>
            </div>
          )
        })}
      </div>

      {/* Charts (client component) */}
      <AnalyticsCharts videos={videos} />

      {/* Top videos table */}
      <div className="card overflow-hidden">
        <div
          className="px-4 py-3 flex items-center gap-2"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <TrendingUp size={13} style={{ color: 'var(--text-muted)' }} />
          <span className="section-header mb-0">Top Videos — Last 30 Days</span>
        </div>
        {videos.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              No analytics data yet — data will appear once the Analytics Agent runs
            </p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Title</th>
                <th>Views</th>
                <th>Watch Hours</th>
                <th>RPM</th>
                <th>CTR</th>
                <th>Revenue</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((v, i) => (
                <tr key={v.id}>
                  <td>
                    <span className="mono text-xs" style={{ color: 'var(--text-muted)' }}>
                      {String(i + 1).padStart(2, '0')}
                    </span>
                  </td>
                  <td>
                    <span className="text-sm" style={{ color: 'var(--text-primary)' }}>
                      {v.title ?? v.youtube_video_id}
                    </span>
                  </td>
                  <td>
                    <span className="mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {v.views.toLocaleString()}
                    </span>
                  </td>
                  <td>
                    <span className="mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {Math.round(v.watch_time_minutes / 60).toLocaleString()}h
                    </span>
                  </td>
                  <td>
                    <span className="mono text-xs font-semibold" style={{ color: 'var(--green)' }}>
                      ${v.rpm.toFixed(2)}
                    </span>
                  </td>
                  <td>
                    <span className="mono text-xs" style={{ color: 'var(--blue)' }}>
                      {v.ctr.toFixed(1)}%
                    </span>
                  </td>
                  <td>
                    <span className="mono text-xs font-bold" style={{ color: 'var(--amber)' }}>
                      ${v.estimated_revenue.toFixed(2)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
