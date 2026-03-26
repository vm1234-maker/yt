'use client'

import { useState } from 'react'
import { Download, CheckCircle, XCircle, Loader2 } from 'lucide-react'

type Status = 'idle' | 'running' | 'success' | 'error'

export function SetupAgentButton() {
  const [status, setStatus] = useState<Status>('idle')
  const [summary, setSummary] = useState<string>('')
  const [runId, setRunId] = useState<string | null>(null)

  async function handleSetup() {
    if (status === 'running') return
    setStatus('running')
    setSummary('')

    try {
      const res = await fetch('/api/run-agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent: 'setup', input: {} }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setRunId(data.run_id)

      // Poll until done
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        if (attempts > 120) {
          clearInterval(poll)
          setStatus('error')
          setSummary('Timed out waiting for setup to complete')
          return
        }
        const r = await fetch(`/api/agent-status/${data.run_id}`)
        if (!r.ok) return
        const d = await r.json()
        if (d.status === 'success') {
          clearInterval(poll)
          setStatus('success')
          setSummary(d.full_output?.summary || 'All assets downloaded')
        } else if (d.status === 'error' || d.status === 'failed') {
          clearInterval(poll)
          setStatus('error')
          setSummary(d.full_output?.error || 'Setup failed — check agent logs')
        }
      }, 3000)
    } catch (err) {
      setStatus('error')
      setSummary(err instanceof Error ? err.message : 'Unexpected error')
    }
  }

  const icons: Record<Status, React.ReactNode> = {
    idle:    <Download className="w-4 h-4" />,
    running: <Loader2 className="w-4 h-4 animate-spin" />,
    success: <CheckCircle className="w-4 h-4" />,
    error:   <XCircle className="w-4 h-4" />,
  }

  const labels: Record<Status, string> = {
    idle:    'Download All Assets',
    running: 'Downloading…',
    success: 'Assets Ready',
    error:   'Setup Failed',
  }

  const colours: Record<Status, string> = {
    idle:    'bg-blue-600 hover:bg-blue-500 text-white',
    running: 'bg-blue-700 text-white cursor-not-allowed',
    success: 'bg-emerald-600 text-white cursor-default',
    error:   'bg-red-600 hover:bg-red-500 text-white',
  }

  return (
    <div className="flex flex-col items-end gap-1.5">
      <button
        onClick={handleSetup}
        disabled={status === 'running' || status === 'success'}
        className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${colours[status]}`}
      >
        {icons[status]}
        {labels[status]}
      </button>
      {summary && (
        <p className={`text-xs max-w-xs text-right ${status === 'error' ? 'text-red-400' : 'text-emerald-400'}`}>
          {summary}
        </p>
      )}
      {status === 'success' && runId && (
        <p className="text-xs text-gray-500">run {runId.slice(0, 8)}</p>
      )}
    </div>
  )
}
