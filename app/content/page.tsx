import { supabaseAdmin } from '@/lib/supabase-admin'
import type { ContentQueueItem } from '@/lib/types'
import { ContentQueueTable } from '@/components/content-queue-table'

export default async function ContentPage() {
  const { data } = await supabaseAdmin
    .from('content_queue')
    .select('*')
    .order('created_at', { ascending: false })

  const queue: ContentQueueItem[] = data ?? []

  const awaiting   = queue.filter(c => c.status === 'awaiting_approval')
  const inProgress = queue.filter(c => c.status === 'in_production' || c.status === 'approved')
  const scheduled  = queue.filter(c => c.status === 'scheduled')

  return (
    <div className="p-6 space-y-6 animate-fade-in-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
            Content Queue
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            {queue.length === 0
              ? 'No content yet — approve a run from the Agents page'
              : `${queue.length} videos — ${awaiting.length} awaiting approval`}
          </p>
        </div>
        {awaiting.length > 0 && (
          <div className="flex items-center gap-2">
            <div
              className="mono text-[10px] px-3 py-1.5 rounded-md"
              style={{
                background: 'var(--amber-glow)',
                border: '1px solid var(--border-accent)',
                color: 'var(--amber)',
                letterSpacing: '0.06em',
              }}
            >
              {awaiting.length} NEED REVIEW
            </div>
          </div>
        )}
      </div>

      {/* Summary strip */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Total Queue',       value: queue.length,       color: 'var(--text-primary)' },
          { label: 'Awaiting Approval', value: awaiting.length,    color: 'var(--amber)'        },
          { label: 'In Production',     value: inProgress.length,  color: 'var(--green)'        },
          { label: 'Scheduled',         value: scheduled.length,   color: 'var(--blue)'         },
        ].map(s => (
          <div key={s.label} className="card p-4 flex items-center justify-between">
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{s.label}</span>
            <span className="text-xl font-bold" style={{ color: s.color }}>{s.value}</span>
          </div>
        ))}
      </div>

      <ContentQueueTable initialQueue={queue} />
    </div>
  )
}
