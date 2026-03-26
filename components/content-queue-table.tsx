'use client'
import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import type { ContentQueueItem } from '@/lib/types'
import { ContentActions } from './content-actions'
import { Video, Eye, Calendar, ImageIcon, Music, Sparkles } from 'lucide-react'

const statusConfig: Record<string, { label: string; badgeClass: string }> = {
  awaiting_approval: { label: 'Awaiting Approval', badgeClass: 'badge badge-pending' },
  in_production:     { label: 'In Production',     badgeClass: 'badge badge-running' },
  approved:          { label: 'Approved',           badgeClass: 'badge' },
  scheduled:         { label: 'Scheduled',          badgeClass: 'badge badge-scheduled' },
  draft:             { label: 'Draft',              badgeClass: 'badge badge-idle' },
  uploaded:          { label: 'Uploaded',           badgeClass: 'badge badge-idle' },
  rejected:          { label: 'Rejected',           badgeClass: 'badge badge-error' },
}

const priorityColors: Record<string, string> = {
  high:   'var(--amber)',
  medium: 'var(--blue)',
  low:    'var(--text-muted)',
}

const nicheBadgeStyle = {
  background: 'var(--blue-glow)',
  border: '1px solid rgba(99,102,241,0.2)',
  color: 'var(--blue)',
}

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface Props {
  initialQueue: ContentQueueItem[]
}

export function ContentQueueTable({ initialQueue }: Props) {
  const [queue, setQueue] = useState<ContentQueueItem[]>(initialQueue)

  useEffect(() => {
    const channel = supabase
      .channel('content_queue_live')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'content_queue' },
        (payload) => {
          if (payload.eventType === 'INSERT') {
            setQueue(prev => [payload.new as ContentQueueItem, ...prev])
          } else if (payload.eventType === 'UPDATE') {
            setQueue(prev => prev.map(item =>
              item.id === (payload.new as ContentQueueItem).id
                ? (payload.new as ContentQueueItem)
                : item
            ))
          } else if (payload.eventType === 'DELETE') {
            setQueue(prev => prev.filter(item => item.id !== (payload.old as ContentQueueItem).id))
          }
        }
      )
      .subscribe()
    return () => { supabase.removeChannel(channel) }
  }, [])

  const awaiting = queue.filter(c => c.status === 'awaiting_approval')

  return (
    <>
      {/* Content table */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 flex items-center gap-2" style={{ borderBottom: '1px solid var(--border)' }}>
          <Video size={13} style={{ color: 'var(--text-muted)' }} />
          <span className="section-header mb-0">All Videos</span>
        </div>

        {queue.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              No content yet — approve a run from the Agents page
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title / Niche</th>
                  <th>Status</th>
                  <th>Length</th>
                  <th>Target RPM</th>
                  <th>Assets</th>
                  <th>Priority</th>
                  <th>Created</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {queue.map(item => {
                  const sc = statusConfig[item.status] ?? statusConfig.draft
                  const thumbnailReady = item.thumbnail_url !== null
                  const audioReady = item.audio_url !== null
                  return (
                    <tr key={item.id}>
                      <td style={{ maxWidth: 280 }}>
                        <div className="text-sm font-medium leading-snug" style={{ color: 'var(--text-primary)' }}>
                          {item.title}
                        </div>
                        {item.niche && (
                          <span className="mono text-[10px] px-1.5 py-0.5 rounded mt-1 inline-block" style={nicheBadgeStyle}>
                            {item.niche}
                          </span>
                        )}
                      </td>
                      <td>
                        <span className={sc.badgeClass}>{sc.label}</span>
                      </td>
                      <td>
                        <span className="mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                          {item.length_hours !== null ? `${item.length_hours}h` : '—'}
                        </span>
                      </td>
                      <td>
                        <span className="mono text-xs font-semibold" style={{ color: 'var(--green)' }}>
                          {item.target_rpm !== null ? `$${item.target_rpm.toFixed(2)}` : '—'}
                        </span>
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <span title="Thumbnail">
                            <ImageIcon size={12} style={{ color: thumbnailReady ? 'var(--green)' : 'var(--text-muted)' }} />
                          </span>
                          <span title="Audio">
                            <Music size={12} style={{ color: audioReady ? 'var(--green)' : 'var(--text-muted)' }} />
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className="mono text-[10px] font-bold uppercase"
                          style={{ color: priorityColors[item.priority] ?? priorityColors.medium, letterSpacing: '0.06em' }}>
                          {item.priority}
                        </span>
                      </td>
                      <td>
                        <span className="mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
                          {formatDate(item.created_at)}
                        </span>
                      </td>
                      <td>
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            className="flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium transition-colors"
                            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                            title="Preview"
                          >
                            <Eye size={10} />
                          </button>
                          {item.status === 'awaiting_approval' && (
                            <ContentActions id={item.id} variant="row" />
                          )}
                          {item.status === 'scheduled' && item.scheduled_for && (
                            <div className="flex items-center gap-1">
                              <Calendar size={10} style={{ color: 'var(--blue)' }} />
                              <span className="mono text-[10px]" style={{ color: 'var(--blue)' }}>
                                {formatDate(item.scheduled_for)}
                              </span>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail panel for awaiting approval items */}
      {awaiting.length > 0 && (
        <div className="space-y-3 mt-6">
          <p className="section-header">Pending Review</p>
          <div className="grid grid-cols-2 gap-4">
            {awaiting.map(item => (
              <div key={item.id} className="card card-amber glow-amber">
                <div className="p-4" style={{ borderBottom: '1px solid var(--border-accent)' }}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-bold leading-snug" style={{ color: 'var(--text-primary)' }}>
                        {item.title}
                      </h3>
                      {item.description && (
                        <p className="text-xs mt-2 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                          {item.description}
                        </p>
                      )}
                    </div>
                    <div className="flex-shrink-0">
                      <Sparkles size={16} style={{ color: 'var(--amber)' }} />
                    </div>
                  </div>
                </div>
                <div className="p-4 space-y-3">
                  {item.tags && item.tags.length > 0 && (
                    <div>
                      <p className="mono text-[9px] font-semibold mb-1.5" style={{ color: 'var(--text-muted)', letterSpacing: '0.08em' }}>
                        TAGS
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {item.tags.map(tag => (
                          <span key={tag} className="mono text-[10px] px-1.5 py-0.5 rounded"
                            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                            #{tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { label: 'Length',     value: item.length_hours !== null ? `${item.length_hours}h` : '—' },
                      { label: 'Target RPM', value: item.target_rpm !== null ? `$${item.target_rpm.toFixed(2)}` : '—' },
                      { label: 'Niche',      value: item.niche ?? '—' },
                    ].map(m => (
                      <div key={m.label}>
                        <p className="mono text-[9px]" style={{ color: 'var(--text-muted)', letterSpacing: '0.08em' }}>{m.label}</p>
                        <p className="text-sm font-semibold mt-0.5" style={{ color: 'var(--text-primary)' }}>{m.value}</p>
                      </div>
                    ))}
                  </div>
                  <ContentActions id={item.id} variant="card" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
