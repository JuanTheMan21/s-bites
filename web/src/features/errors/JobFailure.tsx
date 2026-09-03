import type { JobView } from '@/domain/job'
import { FailureCard } from './FailureCard'
import { ResumeButton } from './ResumeButton'

export function JobFailure({ job }: { job: JobView }) {
  return (
    <div className="flex flex-col gap-5">
      <FailureCard error={job.error} />
      <ResumeButton jobId={job.jobId} />
    </div>
  )
}
