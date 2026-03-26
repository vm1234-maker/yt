export type AgentStatus = 'running' | 'success' | 'error' | 'idle'

export interface AgentRun {
  id: string
  agent_name: string
  status: AgentStatus
  input: Record<string, unknown> | null
  output_summary: string | null
  full_output: {
    log?: string[]
    result?: Record<string, unknown>
    progress?: number
  } | null
  started_at: string
  finished_at: string | null
  duration_ms: number | null
}

export type ContentStatus =
  | 'draft'
  | 'awaiting_approval'
  | 'approved'
  | 'in_production'
  | 'scheduled'
  | 'uploaded'
  | 'rejected'

export interface ContentQueueItem {
  id: string
  title: string
  niche: string | null
  status: ContentStatus
  length_hours: number | null
  target_rpm: number | null
  description: string | null
  tags: string[] | null
  thumbnail_url: string | null
  audio_url: string | null
  video_url: string | null
  youtube_video_id: string | null
  scheduled_for: string | null
  priority: 'high' | 'medium' | 'low'
  created_at: string
  approved_at: string | null
}

export interface VideoAnalytics {
  id: string
  youtube_video_id: string
  title: string | null
  recorded_at: string
  views: number
  watch_time_minutes: number
  rpm: number
  ctr: number
  avg_view_duration_seconds: number
  estimated_revenue: number
}

export interface ChannelMetrics {
  id: string
  recorded_at: string
  total_views: number
  total_watch_hours: number
  /** @deprecated Prefer total_subscribers / subscribers_gained (migration 002) */
  subscribers?: number
  total_subscribers?: number
  subscribers_gained?: number
  estimated_revenue: number
  avg_rpm: number
  avg_ctr: number
  period_start: string | null
  period_end: string | null
}
