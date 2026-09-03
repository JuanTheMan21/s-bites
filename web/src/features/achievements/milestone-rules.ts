import type { JobView } from '@/domain/job'

export interface Milestone {
  id: string
  label: string
}

const TEN_MINUTES_MS = 600_000
const TIER_TWO_HEAVY_THRESHOLD = 0.5

function isTierTwoHeavy(job: JobView): boolean {
  if (job.segments.length === 0) return false
  const tier2 = job.segments.filter((s) => s.tier === 2).length
  return tier2 / job.segments.length >= TIER_TWO_HEAVY_THRESHOLD
}

/** Every milestone is a pure derived fact about the job list, never server-persisted state --
 * see seen-store.ts's docstring for why this app has no backend achievements endpoint. */
export function computeMilestones(jobs: JobView[]): Milestone[] {
  const succeeded = jobs.filter((j) => j.status === 'succeeded')
  const milestones: Milestone[] = []

  if (succeeded.length >= 1) milestones.push({ id: 'first-video', label: 'First video made' })
  if (succeeded.length >= 5) milestones.push({ id: 'five-videos', label: '5 videos made' })
  if (succeeded.some((j) => j.targetDurationMs >= TEN_MINUTES_MS)) {
    milestones.push({ id: 'ten-minute', label: 'First 10-minute video' })
  }
  if (succeeded.some(isTierTwoHeavy)) {
    milestones.push({ id: 'tier-two-heavy', label: 'Mostly-animated video' })
  }

  return milestones
}
