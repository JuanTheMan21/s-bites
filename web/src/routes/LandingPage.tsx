import { MilestoneRow } from '@/features/achievements/MilestoneRow'
import { JobCard } from '@/features/dashboard/JobCard'
import { useJobsQuery } from '@/features/jobs/use-jobs'
import { PromptComposer } from '@/features/submission/PromptComposer'

export function LandingPage() {
  const { data: jobs } = useJobsQuery()
  const recent = (jobs ?? []).slice(0, 3)

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-10 px-6 py-16">
      <div className="flex flex-col gap-3">
        <h1 className="font-display text-4xl leading-[0.95] text-ink-900 sm:text-5xl">
          Turn a topic into a narrated explainer.
        </h1>
        <p className="text-ink-500">
          Type what you want explained. We'll outline it, narrate it, and render it while you
          watch.
        </p>
      </div>
      <PromptComposer />
      <MilestoneRow />
      {recent.length > 0 && (
        <div className="flex flex-col gap-3">
          <p className="font-mono text-xs tracking-wide text-ink-500 uppercase">Recent</p>
          {recent.map((job) => (
            <JobCard key={job.jobId} job={job} />
          ))}
        </div>
      )}
    </div>
  )
}
