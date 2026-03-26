'use client'

import { useTransition } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { approveContent, rejectContent } from '@/app/content/actions'

interface ContentActionsProps {
  id: string
  variant?: 'row' | 'card'
}

export function ContentActions({ id, variant = 'row' }: ContentActionsProps) {
  const [isPending, startTransition] = useTransition()

  function handleApprove() {
    startTransition(() => {
      approveContent(id)
    })
  }

  function handleReject() {
    startTransition(() => {
      rejectContent(id)
    })
  }

  if (variant === 'card') {
    return (
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={handleApprove}
          disabled={isPending}
          className="flex-1 flex items-center justify-center gap-2 py-2 rounded-md text-sm font-semibold transition-colors disabled:opacity-50"
          style={{
            background: 'var(--green-glow)',
            border: '1px solid rgba(16,185,129,0.3)',
            color: 'var(--green)',
          }}
        >
          <CheckCircle2 size={14} />
          {isPending ? 'Saving…' : 'Approve & Queue'}
        </button>
        <button
          onClick={handleReject}
          disabled={isPending}
          className="flex-1 flex items-center justify-center gap-2 py-2 rounded-md text-sm font-semibold transition-colors disabled:opacity-50"
          style={{
            background: 'var(--red-glow)',
            border: '1px solid rgba(239,68,68,0.3)',
            color: 'var(--red)',
          }}
        >
          <XCircle size={14} />
          {isPending ? '…' : 'Reject'}
        </button>
      </div>
    )
  }

  return (
    <>
      <button
        onClick={handleApprove}
        disabled={isPending}
        className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-semibold transition-colors disabled:opacity-50"
        style={{
          background: 'var(--green-glow)',
          border: '1px solid rgba(16,185,129,0.25)',
          color: 'var(--green)',
        }}
      >
        <CheckCircle2 size={10} />
        {isPending ? '…' : 'Approve'}
      </button>
      <button
        onClick={handleReject}
        disabled={isPending}
        className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-semibold transition-colors disabled:opacity-50"
        style={{
          background: 'var(--red-glow)',
          border: '1px solid rgba(239,68,68,0.25)',
          color: 'var(--red)',
        }}
      >
        <XCircle size={10} />
        {isPending ? '…' : 'Reject'}
      </button>
    </>
  )
}
