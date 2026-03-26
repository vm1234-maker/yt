'use client'

import { useState } from 'react'
import { Play, Loader2 } from 'lucide-react'

interface Props {
  onTriggered?: (pipelineRunId: string) => void
}

export function RunPipelineMiniButton({ onTriggered }: Props) {
  const [loading, setLoading] = useState(false)

  async function handleRun() {
    setLoading(true)
    try {
      const res = await fetch('/api/run-pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: {} }),
      })
      const data = await res.json()
      if (data.pipeline_run_id) onTriggered?.(data.pipeline_run_id)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleRun}
      disabled={loading}
      className="w-7 h-7 rounded-md flex items-center justify-center transition-colors disabled:opacity-50"
      style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
      title="Run full pipeline"
    >
      {loading ? (
        <Loader2 size={10} className="animate-spin" style={{ color: 'var(--green)' }} />
      ) : (
        <Play size={10} />
      )}
    </button>
  )
}
