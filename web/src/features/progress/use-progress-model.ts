import { deriveCompletedPhases, type PipelinePhase, type StageEvent } from '@/domain/stage'
import type { JobView, SegmentView } from '@/domain/job'
import { useJobStream } from './use-job-stream'

/** Real progress within the *current* phase, from segment data already on the job -- never
 * faked. `null` for phases with no natural per-segment signal (outline/budget/visuals/finalize
 * are each one atomic, whole-video node with nothing to fraction). */
export function derivePhaseProgress(phase: PipelinePhase, segments: SegmentView[]): number | null {
  if (segments.length === 0) return null
  switch (phase) {
    case 'voice':
      return segments.filter((s) => s.durationMs !== null).length / segments.length
    case 'scenes':
      return segments.filter((s) => s.hasScene).length / segments.length
    case 'render':
      return segments.filter((s) => s.clipKey !== null).length / segments.length
    default:
      return null
  }
}

export function deriveCurrentPhase(events: StageEvent[]): PipelinePhase {
  const last = [...events].reverse().find((e) => e.kind === 'transition')
  return last && last.kind === 'transition' ? last.phase : 'outline'
}

export function deriveActiveSegmentIndex(events: StageEvent[]): number | null {
  const last = [...events]
    .reverse()
    .find((e) => e.kind === 'transition' && e.segmentIndex !== undefined)
  return last && last.kind === 'transition' ? (last.segmentIndex ?? null) : null
}

/** Everything a richer progress view needs, in one place -- `LiveProgress.tsx` composes
 * components off this rather than deriving anything itself. */
export function useProgressModel(job: JobView) {
  const { events, connection } = useJobStream(job.jobId, job)

  const currentPhase = deriveCurrentPhase(events)
  const completedPhases = deriveCompletedPhases(job.segments)
  if (job.status === 'succeeded') completedPhases.add('finalize')

  return {
    currentPhase,
    completedPhases,
    phaseProgress: derivePhaseProgress(currentPhase, job.segments),
    activeSegmentIndex: deriveActiveSegmentIndex(events),
    connection,
    events,
  }
}
