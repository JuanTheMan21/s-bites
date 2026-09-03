import { useState } from 'react'
import type { JobView } from '@/domain/job'
import { JobFailure } from '@/features/errors/JobFailure'
import { LiveProgress } from '@/features/progress/LiveProgress'
import { SegmentInspector } from '@/features/segments/SegmentInspector'
import { JobHeader } from './JobHeader'
import { JobResult } from './JobResult'

/** Pure presentation -- no data fetching, so it's the one place both entry points (a job
 * embedded on the Studio page right after submit, and a durable /jobs/:jobId visit) render an
 * identical experience. `JobStageLoader` is the only thing that fetches `job`. */
export function JobStage({ job }: { job: JobView }) {
  const [openIndex, setOpenIndex] = useState<number | null>(null)
  const openSegment = job.segments.find((s) => s.index === openIndex) ?? null

  return (
    <div className="flex flex-col gap-6">
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
