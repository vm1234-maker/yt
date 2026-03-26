import type { AgentRun } from '@/lib/types'

/** Latest run per `agent_name` (by `started_at`). */
export function latestRunPerAgent(runs: AgentRun[]): Record<string, AgentRun> {
  const map: Record<string, AgentRun> = {}
  for (const run of runs) {
    const existing = map[run.agent_name]
    if (!existing || run.started_at > existing.started_at) {
      map[run.agent_name] = run
    }
  }
  return map
}
