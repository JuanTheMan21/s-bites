import { Pill } from '@/components/Pill'
import { useJobsQuery } from '@/features/jobs/use-jobs'
import { computeMilestones } from './milestone-rules'

export function MilestoneRow() {
  const { data: jobs } = useJobsQuery()
  const milestones = computeMilestones(jobs ?? [])
  if (milestones.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-2">
      {milestones.map((milestone) => (
        <Pill key={milestone.id} tone="accent">
          {milestone.label}
        </Pill>
      ))}
    </div>
  )
}
