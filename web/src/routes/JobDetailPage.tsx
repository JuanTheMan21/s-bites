import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { ApiError } from '@/adapters/job-adapter'
import { EmptyState } from '@/components/EmptyState'
import { Skeleton } from '@/components/Skeleton'
import { JobFailure } from '@/features/errors/JobFailure'
import { JobHeader } from '@/features/jobs/JobHeader'
import { JobResult } from '@/features/jobs/JobResult'
import { useJobQuery } from '@/features/jobs/use-job'
import { LiveProgress } from '@/features/progress/LiveProgress'
import { SegmentInspector } from '@/features/segments/SegmentInspector'

export function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const query = useJobQuery(jobId!)
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  if (query.isPending) {
    return (
      <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-16">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (query.isError) {
    const notFound = query.error instanceof ApiError && query.error.status === 404
    return (
      <div className="mx-auto max-w-4xl px-6 py-16">
        <EmptyState
          title={notFound ? 'No such video' : 'Something went wrong'}
          description={notFound ? `No job matches ${jobId}.` : 'Try refreshing the page.'}
        />
      </div>
    )
  }

  const job = query.data
  const openSegment = job.segments.find((s) => s.index === openIndex) ?? null

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-16">
      <JobHeader job={job} />
      {(job.status === 'queued' || job.status === 'running') && (
        <LiveProgress job={job} onOpenSegment={setOpenIndex} />
      )}
      {job.status === 'succeeded' && <JobResult job={job} onOpenSegment={setOpenIndex} />}
      {job.status === 'failed' && <JobFailure job={job} />}
      <SegmentInspector jobId={job.jobId} segment={openSegment} onClose={() => setOpenIndex(null)} />
    </div>
  )
}
