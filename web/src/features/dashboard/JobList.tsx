import { AnimatePresence } from 'motion/react'
import { useMemo, useState } from 'react'
import { EmptyState } from '@/components/EmptyState'
import { Skeleton } from '@/components/Skeleton'
import { Tabs } from '@/components/Tabs'
import { useJobsQuery } from '@/features/jobs/use-jobs'
import { JobCard } from './JobCard'

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'running', label: 'Running' },
  { value: 'succeeded', label: 'Succeeded' },
  { value: 'failed', label: 'Failed' },
]

export function JobList() {
  const { data: jobs, isPending } = useJobsQuery()
  const [filter, setFilter] = useState('all')

  const filtered = useMemo(() => {
    if (!jobs) return []
    if (filter === 'all') return jobs
    if (filter === 'running') return jobs.filter((j) => j.status === 'running' || j.status === 'queued')
    return jobs.filter((j) => j.status === filter)
  }, [jobs, filter])

  if (isPending) {
    return (
      <div className="flex flex-col gap-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
    )
  }

  if (!jobs || jobs.length === 0) {
    return (
      <EmptyState
        title="No videos yet"
        description="Submit a topic above and it will show up here as it's made."
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <Tabs value={filter} onValueChange={setFilter} options={FILTERS} />
      <div className="flex flex-col gap-3">
        <AnimatePresence>
          {filtered.map((job) => (
            <JobCard key={job.jobId} job={job} />
          ))}
        </AnimatePresence>
        {filtered.length === 0 && (
          <EmptyState title="Nothing here" description="No videos match this filter yet." />
        )}
      </div>
    </div>
  )
}
