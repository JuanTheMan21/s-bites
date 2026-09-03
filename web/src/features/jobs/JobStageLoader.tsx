import { ApiError } from '@/adapters/job-adapter'
import { EmptyState } from '@/components/EmptyState'
import { Skeleton } from '@/components/Skeleton'
import { useJobQuery } from './use-job'
import { JobStage } from './JobStage'

/** The only place `useJobQuery` lives -- both `/jobs/:jobId` and a job just submitted from `/`
 * (same route, StudioPage) go through this, so loading and 404 behaviour can never diverge
 * between them. */
export function JobStageLoader({ jobId }: { jobId: string }) {
  const query = useJobQuery(jobId)

  if (query.isPending) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (query.isError) {
    const notFound = query.error instanceof ApiError && query.error.status === 404
    return (
      <EmptyState
        title={notFound ? 'No such video' : 'Something went wrong'}
        description={notFound ? `No job matches ${jobId}.` : 'Try refreshing the page.'}
      />
    )
  }

  return <JobStage job={query.data} />
}
