'use client'
import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import type { AgentRun } from '@/lib/types'
import { Cpu, Clock } from 'lucide-react'

interface Props {
  initialRuns: AgentRun[]
}

const AGENT_META: Record<string, { name: string; role: string }> = {
  pipeline:   { name: 'Full Pipeline',    role: 'End-to-end orchestrator' },
  strategy:   { name: 'Strategy Agent',   role: 'Content Strategist & ROI Optimizer' },
  research:   { name: 'Research Agent',   role: 'YouTube Trend Analyst' },
  content:    { name: 'Content Agent',    role: 'Title, Thumbnail & Metadata Creator' },
  production: { name: 'Production Agent', role: 'Audio Generation & FFmpeg Renderer' },
  upload:     { name: 'Upload Agent',     role: 'YouTube Data API v3 Publisher' },
  analytics:  { name: 'Analytics Agent',  role: 'Performance Monitor & Reporter' },
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

export function AgentStatusGrid({ initialRuns }: Props) {
  const [runMap, setRunMap] = useState<Record<string, AgentRun>>(() => {
    const map: Record<string, AgentRun> = {}
    for (const run of initialRuns) {
      const existing = map[run.agent_name]
      if (!existing || run.started_at > existing.started_at) {
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
          if (!updated?.agent_name) return
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
        const lastRun = run ? relativeTime(run.started_at) : '—'

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
