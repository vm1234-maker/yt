'use client'

import { useState } from 'react'
import { PlayCircle, Loader2, MessageSquare, CheckCircle2, XCircle, ChevronDown, ChevronUp } from 'lucide-react'

type DiscussionTurn = {
  round: number
  agent: string
  ts: string
  message: string
}

type PipelineState =
  | { phase: 'idle' }
  | { phase: 'running'; pipeline_run_id: string }
  | { phase: 'paused'; pipeline_run_id: string; step: string; content_id?: string }
  | { phase: 'complete'; youtube_video_id?: string; discussion: DiscussionTurn[] }
  | { phase: 'error'; message: string; step: string }

const AGENT_COLORS: Record<string, string> = {
  'Research Agent': 'var(--blue)',
  'Strategy Agent': 'var(--amber)',
  'Content Agent':  'var(--green)',
}

const STEP_LABELS: Record<string, string> = {
  research:          'Step 1/6 — Research Agent',
  brainstorm:        'Step 2/6 — Brainstorm Round',
  content:           'Step 3/6 — Content Agent',
  approval:          'Step 4/6 — Awaiting Approval',
  approval_timeout:  'Step 4/6 — Approval Timeout',
  production:        'Step 5/6 — Production Agent',
  upload:            'Step 6/6 — Upload Agent',
  complete:          'Pipeline Complete',
}

export function RunPipelineButton() {
  const [state, setState] = useState<PipelineState>({ phase: 'idle' })
  const [showDiscussion, setShowDiscussion] = useState(false)
  const [pollCount, setPollCount] = useState(0)

  async function startPipeline() {
    setState({ phase: 'running', pipeline_run_id: '' })
    try {
      const res = await fetch('/api/run-pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: {} }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed to start pipeline')
      setState({ phase: 'running', pipeline_run_id: data.pipeline_run_id })
      pollStatus(data.pipeline_run_id, 0)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setState({ phase: 'error', message: msg, step: 'start' })
    }
  }

  async function pollStatus(runId: string, attempt: number) {
    if (attempt > 720) {
      // 720 × 5s = 1hr max poll
      setState({ phase: 'error', message: 'Pipeline timed out after 1 hour', step: 'timeout' })
      return
    }
    await new Promise((r) => setTimeout(r, 5000))
    setPollCount(attempt + 1)

    try {
      const res = await fetch(`/api/agent-status/${runId}`)
      if (!res.ok) { pollStatus(runId, attempt + 1); return }
      const run = await res.json()
      const output = run.full_output || {}
      const step: string = output.step || ''

      if (run.status === 'success' && step === 'complete') {
        setState({
          phase: 'complete',
          youtube_video_id: output.youtube_video_id,
          discussion: output.discussion || [],
        })
        return
      }

      if (run.status === 'error') {
        setState({ phase: 'error', message: run.output_summary || 'Unknown error', step })
        return
      }

      if (step === 'approval' || step === 'approval_timeout') {
        setState({ phase: 'paused', pipeline_run_id: runId, step, content_id: output.content_id })
        if (step !== 'approval_timeout') {
          pollStatus(runId, attempt + 1)
        }
        return
      }

      // Still running — keep polling
      setState({ phase: 'running', pipeline_run_id: runId })
      pollStatus(runId, attempt + 1)
    } catch {
      pollStatus(runId, attempt + 1)
    }
  }

  const isRunning = state.phase === 'running'

  return (
    <div
      className="rounded-lg p-4 space-y-3"
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
      }}
    >
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Full Pipeline
          </p>
          <p className="mono text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
            Research → Brainstorm → Content → Approval → Production → Upload
          </p>
        </div>

        <button
          onClick={startPipeline}
          disabled={isRunning}
          className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-semibold transition-opacity disabled:opacity-50"
          style={{
            background: isRunning ? 'var(--bg-surface)' : 'var(--amber)',
            color: isRunning ? 'var(--text-muted)' : '#000',
            border: isRunning ? '1px solid var(--border)' : 'none',
          }}
        >
          {isRunning ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              Running…
            </>
          ) : (
            <>
              <PlayCircle size={14} />
              Run Full Pipeline
            </>
          )}
        </button>
      </div>

      {/* Status messages */}
      {state.phase === 'running' && (
        <div
          className="flex items-center gap-2 px-3 py-2 rounded mono text-[11px]"
          style={{ background: 'var(--bg-surface)', color: 'var(--blue)', border: '1px solid var(--border)' }}
        >
          <Loader2 size={11} className="animate-spin shrink-0" />
          <span>Pipeline running — agents are discussing and producing… (poll #{pollCount})</span>
        </div>
      )}

      {state.phase === 'paused' && (
        <div
          className="flex items-center gap-2 px-3 py-2 rounded mono text-[11px]"
          style={{ background: 'rgba(245,158,11,0.08)', color: 'var(--amber)', border: '1px solid rgba(245,158,11,0.2)' }}
        >
          <MessageSquare size={11} className="shrink-0" />
          <span>
            {state.step === 'approval_timeout'
              ? 'Approval timeout — check Content page to approve manually'
              : 'Waiting for approval — go to Content tab to approve or reject'}
            {state.content_id && ` (ID: ${state.content_id.slice(0, 8)})`}
          </span>
        </div>
      )}

      {state.phase === 'complete' && (
        <div
          className="flex items-center gap-2 px-3 py-2 rounded mono text-[11px]"
          style={{ background: 'var(--green-glow)', color: 'var(--green)', border: '1px solid rgba(16,185,129,0.2)' }}
        >
          <CheckCircle2 size={11} className="shrink-0" />
          <span>
            Pipeline complete!
            {state.youtube_video_id && (
              <>
                {' '}Video uploaded:{' '}
                <a
                  href={`https://youtu.be/${state.youtube_video_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline"
                >
                  youtu.be/{state.youtube_video_id}
                </a>
              </>
            )}
          </span>
        </div>
      )}

      {state.phase === 'error' && (
        <div
          className="flex items-center gap-2 px-3 py-2 rounded mono text-[11px]"
          style={{ background: 'rgba(239,68,68,0.08)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}
        >
          <XCircle size={11} className="shrink-0" />
          <span>
            Failed at {STEP_LABELS[state.step] ?? state.step}: {state.message.slice(0, 120)}
          </span>
        </div>
      )}

      {/* Brainstorm discussion log */}
      {state.phase === 'complete' && state.discussion.length > 0 && (
        <div>
          <button
            onClick={() => setShowDiscussion((v) => !v)}
            className="flex items-center gap-1.5 mono text-[10px] w-full text-left"
            style={{ color: 'var(--text-muted)' }}
          >
            <MessageSquare size={10} />
            {showDiscussion ? 'Hide' : 'Show'} brainstorm discussion ({state.discussion.length} turns)
            {showDiscussion ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
          </button>

          {showDiscussion && (
            <div className="mt-2 space-y-2 max-h-72 overflow-y-auto">
              {state.discussion.map((turn, i) => {
                const color = AGENT_COLORS[turn.agent] ?? 'var(--text-secondary)'
                return (
                  <div
                    key={i}
                    className="rounded p-2.5 text-xs"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
                  >
                    <div className="flex items-center gap-2 mb-1.5">
                      <span
                        className="mono text-[10px] font-bold"
                        style={{ color }}
                      >
                        Round {turn.round} · {turn.agent.toUpperCase()}
                      </span>
                      <span className="mono text-[9px]" style={{ color: 'var(--text-muted)' }}>
                        {turn.ts}
                      </span>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      {turn.message}
                    </p>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
