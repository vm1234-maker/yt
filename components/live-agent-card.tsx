'use client'
import { useEffect, useState, useCallback, useRef } from 'react'
import { getSupabaseBrowser } from '@/lib/supabase'
import type { AgentRun } from '@/lib/types'
import { RunAgentButton } from './run-agent-button'
import { RunPipelineMiniButton } from './run-pipeline-mini-button'
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

function formatDuration(ms: number): string {
  if (ms < 60000) return `${Math.round(ms / 1000)}s`
  const m = Math.floor(ms / 60000)
  const s = Math.round((ms % 60000) / 1000)
  return `${m}m ${s}s`
}

function computeStatsFromRuns(runs: AgentRun[], agentId: string) {
  const agentRuns = runs
    .filter((r) => r.agent_name === agentId)
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
  const totalRuns = agentRuns.length
  if (totalRuns === 0) {
    return {
      latest: null as AgentRun | null,
      totalRuns: 0,
      successRate: 0,
      avgDuration: '—',
    }
  }
  const successCount = agentRuns.filter((r) => r.status === 'success').length
  const successRate = Math.round((successCount / totalRuns) * 100 * 10) / 10
  const durationsMs = agentRuns.map((r) => r.duration_ms).filter((d): d is number => d != null)
  const avgMs =
    durationsMs.length > 0 ? durationsMs.reduce((a, b) => a + b, 0) / durationsMs.length : null
  const avgDuration = avgMs != null ? formatDuration(avgMs) : '—'
  return { latest: agentRuns[0], totalRuns, successRate, avgDuration }
}

export function LiveAgentCard({
  agentId,
  agentName,
  agentRole,
  initialRun,
  inputs,
  outputs,
  totalRuns: initialTotalRuns,
  successRate: initialSuccessRate,
  avgDuration: initialAvgDuration,
}: Props) {
  const [run, setRun] = useState<AgentRun | null>(initialRun)
  const [totalRuns, setTotalRuns] = useState(initialTotalRuns)
  const [successRate, setSuccessRate] = useState(initialSuccessRate)
  const [avgDuration, setAvgDuration] = useState(initialAvgDuration)
  const logRef = useRef<HTMLDivElement>(null)

  const refresh = useCallback(async () => {
    const res = await fetch('/api/agents', { cache: 'no-store' })
    if (!res.ok) return
    const runs: AgentRun[] = await res.json()
    const { latest, totalRuns: tr, successRate: sr, avgDuration: ad } = computeStatsFromRuns(runs, agentId)
    setRun(latest)
    setTotalRuns(tr)
    setSuccessRate(sr)
    setAvgDuration(ad)
  }, [agentId])

  // Hydrate from server props on navigation; resync aggregates
  useEffect(() => {
    setRun(initialRun)
    setTotalRuns(initialTotalRuns)
    setSuccessRate(initialSuccessRate)
    setAvgDuration(initialAvgDuration)
  }, [initialRun?.id, initialTotalRuns, initialSuccessRate, initialAvgDuration])

  useEffect(() => {
    void refresh()
  }, [refresh])

  // Any insert/update for this agent_name → refetch (latest run + stats)
  useEffect(() => {
    const sb = getSupabaseBrowser()
    if (!sb) return
    const channel = sb
      .channel(`agent_name_${agentId}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'agent_runs',
          filter: `agent_name=eq.${agentId}`,
        },
        () => {
          void refresh()
        }
      )
      .subscribe()
    return () => {
      sb.removeChannel(channel)
    }
  }, [agentId, refresh])

  // While running, poll in case Realtime lags on partial updates
  useEffect(() => {
    if (run?.status !== 'running') return
    const interval = setInterval(() => {
      void refresh()
    }, 5000)
    return () => clearInterval(interval)
  }, [run?.status, refresh])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [run?.full_output?.log])

  const status = run?.status ?? 'idle'
  const logs = run?.full_output?.log ?? []
  const progress = run?.full_output?.progress

  return (
    <div className="card flex flex-col">
      <div className="p-4 flex items-start justify-between gap-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-start gap-3 min-w-0">
          <div
            className="w-9 h-9 rounded-md flex items-center justify-center flex-shrink-0"
            style={{
              background: status === 'running' ? 'var(--green-glow)' : 'var(--bg-elevated)',
              border: `1px solid ${status === 'running' ? 'rgba(16,185,129,0.2)' : 'var(--border)'}`,
            }}
          >
            {status === 'running' ? (
              <Loader2 size={15} className="animate-spin" style={{ color: 'var(--green)' }} />
            ) : (
              <Cpu size={15} style={{ color: 'var(--text-secondary)' }} />
            )}
          </div>
          <div>
            <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{agentName}</span>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>{agentRole}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={`badge ${status === 'running' ? 'badge-running' : status === 'error' ? 'badge-error' : 'badge-idle'}`}
          >
            {status}
          </span>
          {agentId === 'pipeline' ? (
            <RunPipelineMiniButton
              onTriggered={(pipelineRunId) => {
                setRun({
                  id: pipelineRunId,
                  agent_name: 'pipeline',
                  status: 'running',
                  input: null,
                  output_summary: null,
                  full_output: null,
                  started_at: new Date().toISOString(),
                  finished_at: null,
                  duration_ms: null,
                })
                void refresh()
              }}
            />
          ) : (
            <RunAgentButton
              agentId={agentId}
              onTriggered={(runId) => {
                setRun((prev) =>
                  prev
                    ? { ...prev, id: runId, status: 'running' }
                    : {
                        id: runId,
                        agent_name: agentId,
                        status: 'running',
                        input: null,
                        output_summary: null,
                        full_output: null,
                        started_at: new Date().toISOString(),
                        finished_at: null,
                        duration_ms: null,
                      }
                )
                void refresh()
              }}
            />
          )}
        </div>
      </div>

      <div className="grid grid-cols-4 divide-x" style={{ borderBottom: '1px solid var(--border)', borderColor: 'var(--border)' }}>
        {[
          { label: 'RUNS', value: totalRuns },
          { label: 'SUCCESS', value: totalRuns === 0 ? '—' : `${successRate}%` },
          { label: 'AVG TIME', value: avgDuration },
          { label: 'LAST RUN', value: run ? new Date(run.started_at).toLocaleTimeString() : '—' },
        ].map((m) => (
          <div key={m.label} className="px-3 py-2 text-center" style={{ borderColor: 'var(--border)' }}>
            <div
              className="mono text-[9px] font-semibold"
              style={{ color: 'var(--text-muted)', letterSpacing: '0.08em' }}
            >
              {m.label}
            </div>
            <div className="text-xs font-bold mt-0.5" style={{ color: 'var(--text-primary)' }}>{m.value}</div>
          </div>
        ))}
      </div>

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

      <div className="px-4 py-3 grid grid-cols-2 gap-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <div>
          <p className="mono text-[9px] font-semibold mb-1.5" style={{ color: 'var(--text-muted)', letterSpacing: '0.08em' }}>INPUTS</p>
          <div className="flex flex-wrap gap-1">
            {inputs.map((i) => (
              <span
                key={i}
                className="mono text-[10px] px-1.5 py-0.5 rounded"
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-secondary)',
                }}
              >
                {i}
              </span>
            ))}
          </div>
        </div>
        <div>
          <p className="mono text-[9px] font-semibold mb-1.5" style={{ color: 'var(--text-muted)', letterSpacing: '0.08em' }}>OUTPUTS</p>
          <div className="flex flex-wrap gap-1">
            {outputs.map((o) => (
              <span
                key={o}
                className="mono text-[10px] px-1.5 py-0.5 rounded"
                style={{
                  background: 'var(--amber-glow)',
                  border: '1px solid rgba(245,158,11,0.15)',
                  color: 'var(--amber)',
                }}
              >
                {o}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="p-4">
        <div className="flex items-center gap-1.5 mb-2">
          <SquareTerminal size={11} style={{ color: 'var(--text-muted)' }} />
          <span className="mono text-[9px]" style={{ color: 'var(--text-muted)', letterSpacing: '0.08em' }}>
            {status === 'running' ? 'LIVE LOG' : 'LAST RUN LOG'}
          </span>
        </div>
        <div className="log-terminal" ref={logRef}>
          {logs.length === 0 ? (
            <span style={{ color: 'var(--text-muted)' }}>No runs yet — waiting for first agent run</span>
          ) : (
            logs.map((line, i) => {
              const isWarn = line.includes('WARN')
              const isError = line.includes('ERROR')
              const tsEnd = line.indexOf(']') + 1
              const ts = tsEnd > 0 ? line.slice(0, tsEnd) : ''
              const rest = tsEnd > 0 ? line.slice(tsEnd) : line
              return (
                <div key={i} className={isWarn ? 'log-warn' : isError ? 'log-error' : ''}>
                  {ts && <span className="log-timestamp">{ts}</span>}
                  {rest}
                </div>
              )
            })
          )}
          {status === 'running' && <span className="cursor-blink" style={{ color: 'var(--green)' }}>█</span>}
        </div>
      </div>
    </div>
  )
}
