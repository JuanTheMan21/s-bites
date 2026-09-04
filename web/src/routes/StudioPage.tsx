import { useParams } from 'react-router-dom'
import { MilestoneRow } from '@/features/achievements/MilestoneRow'
import { RecentJobs } from '@/features/dashboard/RecentJobs'
import { JobStageLoader } from '@/features/jobs/JobStageLoader'
import { ComposerSection } from '@/features/submission/ComposerSection'

/** Renders both `/` and `/jobs/:jobId` -- submitting a topic never navigates away from this
 * component, only the URL changes (`PromptComposer`'s `navigate(..., {replace:true})`), so the
 * composer and the live/finished result live on the same page throughout a job's lifecycle. */
export function StudioPage() {
  const { jobId } = useParams<{ jobId?: string }>()

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 px-8 py-16">
      <ComposerSection collapsed={Boolean(jobId)} />
      {jobId ? (
        <JobStageLoader jobId={jobId} />
      ) : (
        <>
          <MilestoneRow />
          <RecentJobs />
        </>
      )}
    </div>
  )
}
