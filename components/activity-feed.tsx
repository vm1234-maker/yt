'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, AlertCircle, Cpu } from 'lucide-react'
import { getSupabaseBrowser } from '@/lib/supabase'
import type { AgentRun } from '@/lib/types'

interface ActivityFeedProps {
  initial: AgentRun[]
}

function eventColor(status: string): string {
  if (status === 'success') return 'var(--green)'
  if (status === 'error') return 'var(--red)'
  return 'var(--blue)'
}

function EventIcon({ status }: { status: string }) {
  if (status === 'success') return <CheckCircle2 size={11} />
  if (status === 'error') return <AlertCircle size={11} />
  return <Cpu size={11} />
}

function relativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function ActivityFeed({ initial }: ActivityFeedProps) {
  const [feed, setFeed] = useState<AgentRun[]>(initial)

  useEffect(() => {
    const sb = getSupabaseBrowser()
    if (!sb) return
    let cancelled = false
    void (async () => {
      const { data } = await sb
        .from('agent_runs')
        .select('*')
        .order('started_at', { ascending: false })
        .limit(30)
      if (cancelled || !data) return
      setFeed(data as AgentRun[])
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const sb = getSupabaseBrowser()
    if (!sb) return
    const channel = sb
      .channel('activity_feed')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'agent_runs' },
        (payload) => {
          setFeed((prev) => [payload.new as AgentRun, ...prev].slice(0, 30))
        }
      )
      .subscribe()

    return () => {
      sb.removeChannel(channel)
    }
  }, [])

  if (feed.length === 0) {
    return (
      <div
        className="card h-[calc(100%-28px)] flex items-center justify-center"
        style={{ minHeight: 200 }}
      >
        <p className="text-xs text-center px-4" style={{ color: 'var(--text-muted)' }}>
          No activity yet —{' '}
          <span style={{ color: 'var(--text-secondary)' }}>run an agent to get started</span>
        </p>
      </div>
    )
  }

  return (
    <div
      className="card h-[calc(100%-28px)] overflow-y-auto"
      style={{ minHeight: 0 }}
    >
      <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
        {feed.map((run, i) => {
          const color = eventColor(run.status)
          return (
            <div
              key={run.id}
              className="p-3 hover:opacity-80 transition-opacity animate-slide-in"
              style={{ animationDelay: `${i * 0.04}s` }}
            >
              <div className="flex items-start gap-2">
                <span className="mt-0.5 flex-shrink-0" style={{ color }}>
                  <EventIcon status={run.status} />
                </span>
                <div className="min-w-0">
                  <p
                    className="text-[11.5px] leading-relaxed"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    {run.output_summary ?? `${run.agent_name} — ${run.status}`}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="mono text-[9.5px]" style={{ color }}>
                      {run.agent_name}
                    </span>
                    <span
                      className="mono text-[9.5px]"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      {relativeTime(run.started_at)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
