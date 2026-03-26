import type { ChannelMetrics } from '@/lib/types'

/** Migration 002 uses total_subscribers + subscribers_gained; legacy rows may have subscribers. */
export function displaySubscriberCount(metrics: ChannelMetrics | null): number {
  if (!metrics) return 0
  const m = metrics as unknown as Record<string, unknown>
  if (typeof m.total_subscribers === 'number') return m.total_subscribers
  if (typeof m.subscribers === 'number') return m.subscribers
  if (typeof m.subscribers_gained === 'number') return m.subscribers_gained
  return 0
}
