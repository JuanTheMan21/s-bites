import { IconTrophy } from '@/components/icons'
import { Pill } from '@/components/Pill'
import { useJobsQuery } from '@/features/jobs/use-jobs'
import { computeMilestones } from './milestone-rules'

/** Each pill is a real, derived fact about the job list (D137: no fabricated points/XP), but a
 * bare unlabeled pill reads as noise out of context -- the trophy icon and "Achievements" label
 * are what turn "First video made" from a stray text fragment into a legible milestone. */
export function MilestoneRow() {
  const { data: jobs } = useJobsQuery()
  const milestones = computeMilestones(jobs ?? [])
  if (milestones.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <span className="font-mono text-xs tracking-wide text-ink-500 uppercase">Achievements</span>
      {milestones.map((milestone) => (
        <Pill key={milestone.id} tone="accent">
          <IconTrophy className="h-3 w-3" />
          {milestone.label}
        </Pill>
      ))}
    </div>
  )
}
