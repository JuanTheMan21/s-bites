import { useJobsQuery } from '@/features/jobs/use-jobs'
import { JobCard } from './JobCard'

export function RecentJobs() {
  const { data: jobs } = useJobsQuery()
  const recent = (jobs ?? []).slice(0, 3)
  if (recent.length === 0) return null

  return (
    <div className="flex flex-col gap-3">
      <p className="font-mono text-xs tracking-wide text-ink-500 uppercase">Recent</p>
      {recent.map((job) => (
        <JobCard key={job.jobId} job={job} />
      ))}
    </div>
  )
}
