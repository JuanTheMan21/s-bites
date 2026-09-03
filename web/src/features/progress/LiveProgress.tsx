import type { JobView } from '@/domain/job'
import { SegmentGrid } from '@/features/segments/SegmentGrid'
import { ElapsedClock } from './ElapsedClock'
import { FrameBudgetMeter } from './FrameBudgetMeter'
import { PlayfulCaption } from './PlayfulCaption'
import { ProductionStrip } from './ProductionStrip'
import { StageLog } from './StageLog'
import { StageTicker } from './StageTicker'
import { useProgressModel } from './use-progress-model'

export function LiveProgress({
  job,
  onOpenSegment,
}: {
  job: JobView
  onOpenSegment: (index: number) => void
}) {
  const { currentPhase, completedPhases, phaseProgress, activeSegmentIndex, connection, events } =
    useProgressModel(job)

  return (
    <div className="flex flex-col gap-6">
      <ProductionStrip
        currentPhase={currentPhase}
        completedPhases={completedPhases}
        phaseProgress={phaseProgress}
      />
      <div className="flex items-center justify-between gap-4">
        <PlayfulCaption key={currentPhase} phase={currentPhase} />
        <div className="flex items-center gap-3">
          {connection === 'reconnecting' && (
            <span className="rounded-full bg-signal-warn/12 px-2.5 py-1 font-mono text-[11px] text-signal-warn">
              Reconnecting…
            </span>
          )}
          <ElapsedClock startedAt={job.createdAt} />
        </div>
      </div>
      <StageTicker events={events} />
      <FrameBudgetMeter segments={job.segments} />
      <SegmentGrid
        segments={job.segments}
        activeSegmentIndex={activeSegmentIndex}
        onOpenSegment={onOpenSegment}
      />
      <StageLog events={events} />
    </div>
  )
}
