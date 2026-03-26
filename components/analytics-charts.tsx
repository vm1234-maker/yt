'use client'

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import type { VideoAnalytics } from '@/lib/types'

interface AnalyticsChartsProps {
  videos: VideoAnalytics[]
}

// Group videos by recorded_at date and sum views per day
function buildViewsData(videos: VideoAnalytics[]) {
  const byDate = new Map<string, number>()
  for (const v of videos) {
    const day = v.recorded_at.slice(0, 10) // 'YYYY-MM-DD'
    byDate.set(day, (byDate.get(day) ?? 0) + v.views)
  }
  return Array.from(byDate.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, views]) => ({
      day: new Date(day).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      views,
    }))
}

// Group by niche derived from title (first word heuristic) and sum revenue
function buildRevenueByNiche(videos: VideoAnalytics[]) {
  const byNiche = new Map<string, number>()
  for (const v of videos) {
    const niche = v.title?.split(' ')[0] ?? 'Other'
    byNiche.set(niche, (byNiche.get(niche) ?? 0) + v.estimated_revenue)
  }
  return Array.from(byNiche.entries())
    .sort(([, a], [, b]) => b - a)
    .slice(0, 6)
    .map(([niche, revenue]) => ({ niche, revenue: Math.round(revenue * 100) / 100 }))
}

// Group by date and sum watch_time_minutes → hours
function buildWatchTimeData(videos: VideoAnalytics[]) {
  const byDate = new Map<string, number>()
  for (const v of videos) {
    const day = v.recorded_at.slice(0, 10)
    byDate.set(day, (byDate.get(day) ?? 0) + v.watch_time_minutes)
  }
  return Array.from(byDate.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, minutes]) => ({
      day: new Date(day).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      hours: Math.round(minutes / 60),
    }))
}

const tooltipStyle = {
  backgroundColor: '#0a0e18',
  border: '1px solid rgba(72,100,170,0.25)',
  borderRadius: '6px',
  color: '#dde5f5',
  fontSize: '11px',
  fontFamily: 'var(--font-geist-mono), monospace',
}

const axisStyle = {
  fill: '#3a4a65',
  fontSize: 10,
  fontFamily: 'var(--font-geist-mono), monospace',
}

function EmptyChart({ label }: { label: string }) {
  return (
    <div
      className="flex items-center justify-center"
      style={{ height: 180 }}
    >
      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
        No analytics data yet
      </p>
    </div>
  )
}

export default function AnalyticsCharts({ videos }: AnalyticsChartsProps) {
  const viewsData = buildViewsData(videos)
  const revenueByNiche = buildRevenueByNiche(videos)
  const watchTimeData = buildWatchTimeData(videos)

  const hasData = videos.length > 0

  return (
    <div className="grid grid-cols-3 gap-4">
      {/* Views over time */}
      <div className="card col-span-2 p-4" style={{ minHeight: 240 }}>
        <p className="section-header mb-4" style={{ color: 'var(--text-muted)' }}>
          Daily Views — Last 30 Days
        </p>
        {!hasData || viewsData.length === 0 ? (
          <EmptyChart label="views" />
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={viewsData} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
              <defs>
                <linearGradient id="viewsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(72,100,170,0.1)" />
              <XAxis dataKey="day" tick={axisStyle} axisLine={false} tickLine={false} interval={2} />
              <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={tooltipStyle}
                labelStyle={{ color: '#6a82a8' }}
                cursor={{ stroke: 'rgba(99,102,241,0.3)', strokeWidth: 1 }}
              />
              <Area
                type="monotone"
                dataKey="views"
                stroke="#6366f1"
                strokeWidth={2}
                fill="url(#viewsGrad)"
                dot={false}
                activeDot={{ r: 4, fill: '#6366f1' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Revenue by niche */}
      <div className="card p-4" style={{ minHeight: 240 }}>
        <p className="section-header mb-4" style={{ color: 'var(--text-muted)' }}>
          Revenue by Niche
        </p>
        {!hasData || revenueByNiche.length === 0 ? (
          <EmptyChart label="revenue" />
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <BarChart
              data={revenueByNiche}
              layout="vertical"
              margin={{ top: 0, right: 8, bottom: 0, left: -8 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(72,100,170,0.1)"
                horizontal={false}
              />
              <XAxis type="number" tick={axisStyle} axisLine={false} tickLine={false} />
              <YAxis
                dataKey="niche"
                type="category"
                tick={axisStyle}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                labelStyle={{ color: '#6a82a8' }}
                cursor={{ fill: 'rgba(99,102,241,0.05)' }}
                formatter={(val) => [`$${val}`, 'Revenue']}
              />
              <Bar dataKey="revenue" fill="#f59e0b" radius={[0, 3, 3, 0]} maxBarSize={14} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Watch hours */}
      <div className="card col-span-3 p-4" style={{ minHeight: 200 }}>
        <p className="section-header mb-4" style={{ color: 'var(--text-muted)' }}>
          Watch Hours Accumulation
        </p>
        {!hasData || watchTimeData.length === 0 ? (
          <EmptyChart label="watch time" />
        ) : (
          <ResponsiveContainer width="100%" height={150}>
            <LineChart
              data={watchTimeData}
              margin={{ top: 4, right: 8, bottom: 0, left: -16 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(72,100,170,0.1)" />
              <XAxis dataKey="day" tick={axisStyle} axisLine={false} tickLine={false} interval={2} />
              <YAxis tick={axisStyle} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={tooltipStyle}
                labelStyle={{ color: '#6a82a8' }}
                cursor={{ stroke: 'rgba(16,185,129,0.3)', strokeWidth: 1 }}
                formatter={(val) => [`${val}h`, 'Watch Hours']}
              />
              <Line
                type="monotone"
                dataKey="hours"
                stroke="#10b981"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#10b981' }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
