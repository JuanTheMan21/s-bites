import { deriveCompletedPhases, type PipelinePhase } from '@/domain/stage'
import type { JobView } from '@/domain/job'
import { SegmentGrid } from '@/features/segments/SegmentGrid'
import { FrameBudgetMeter } from './FrameBudgetMeter'
import { PlayfulCaption } from './PlayfulCaption'
import { ProductionStrip } from './ProductionStrip'
import { StageLog } from './StageLog'
import { useJobStream } from './use-job-stream'

export function LiveProgress({
  job,
  onOpenSegment,
}: {
  job: JobView
  onOpenSegment: (index: number) => void
}) {
  const { events, connection } = useJobStream(job.jobId, job)

  const lastTransition = [...events].reverse().find((e) => e.kind === 'transition')
  const currentPhase: PipelinePhase =
    lastTransition && lastTransition.kind === 'transition' ? lastTransition.phase : 'outline'

  const completedPhases = deriveCompletedPhases(job.segments)
  if (job.status === 'succeeded') completedPhases.add('finalize')

  return (
    <div className="flex flex-col gap-6">
      <ProductionStrip currentPhase={currentPhase} completedPhases={completedPhases} />
      <div className="flex items-center justify-between gap-4">
        <PlayfulCaption key={currentPhase} phase={currentPhase} />
        {connection === 'reconnecting' && (
          <span className="rounded-full bg-signal-warn/12 px-2.5 py-1 font-mono text-[11px] text-signal-warn">
            Reconnecting…
          </span>
        )}
      </div>
      <FrameBudgetMeter segments={job.segments} />
      <SegmentGrid segments={job.segments} onOpenSegment={onOpenSegment} />
      <StageLog events={events} />
    </div>
  )
}
