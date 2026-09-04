import type { JobView } from '@/domain/job'
import { ClipStrip } from './ClipStrip'
import { ClipTrack } from './ClipTrack'
import { ElapsedClock } from './ElapsedClock'
import { PlayfulCaption } from './PlayfulCaption'
import { StageLog } from './StageLog'
import { StageTicker } from './StageTicker'
import { useProgressModel } from './use-progress-model'

/** The direction's signature interaction: one continuous clip track the eye follows top to
 * bottom, replacing six stacked equal-weight widgets with a single focal anchor (a sweeping
 * playhead over a real waveform) plus a REC line above it and a subordinate clip strip below --
 * never a card grid competing with the track for the same visual weight. */
export function LiveProgress({
  job,
  onOpenSegment,
}: {
  job: JobView
  onOpenSegment: (index: number) => void
}) {
  const { currentPhase, completedPhases, phaseProgress, activeSegmentIndex, connection, events } =
    useProgressModel(job)
  const assigned = job.segments.filter((s) => s.tier !== null).length

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-ink-300/25 bg-paper-1 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PlayfulCaption key={currentPhase} phase={currentPhase} />
        <div className="flex items-center gap-3">
          {connection === 'reconnecting' && (
            <span className="rounded-full bg-signal-warn/12 px-2.5 py-1 font-mono text-[11px] text-signal-warn">
              Reconnecting…
            </span>
          )}
          {job.segments.length > 0 && (
            <span className="font-mono text-[11px] text-ink-500 tabular-nums">
              {assigned}/{job.segments.length} tiered
            </span>
          )}
          <ElapsedClock startedAt={job.createdAt} />
        </div>
      </div>
      <ClipTrack
        currentPhase={currentPhase}
        completedPhases={completedPhases}
        phaseProgress={phaseProgress}
        events={events}
        createdAt={job.createdAt}
        segmentCount={job.segments.length}
      />
      <StageTicker events={events} />
      <ClipStrip
        segments={job.segments}
        activeSegmentIndex={activeSegmentIndex}
        onOpenSegment={onOpenSegment}
      />
      <StageLog events={events} />
    </div>
  )
}
