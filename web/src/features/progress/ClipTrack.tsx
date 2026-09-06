import { m } from 'motion/react'
import { PHASE_LABEL, PHASE_ORDER, type PipelinePhase, type StageEvent } from '@/domain/stage'
import { classNames } from '@/components/class-names'
import { IconPlayhead } from '@/components/icons'
import { useSmoothProgress } from './use-smooth-progress'
import { WaveScope } from './WaveScope'

interface Props {
  currentPhase: PipelinePhase | null
  completedPhases: Set<PipelinePhase>
  /** 0..1 within the active phase, or null when that phase has no per-segment signal
   * (`use-progress-model.ts::derivePhaseProgress`). Drives the fill between ticks. */
  phaseProgress: number | null
  events: StageEvent[]
  createdAt: string
  /** Real segment count -- seeds the waveform's own shape (`WaveScope`) so the track's texture
   * stays a deterministic function of the job, not `Math.random()` jitter (D137). */
  segmentCount: number
}

function formatTimecode(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(totalSeconds / 60)}:${String(totalSeconds % 60).padStart(2, '0')}`
}

/** Real per-phase start times, read off the first transition event that entered each phase --
 * `event.at` is a client receipt timestamp (`stage-adapter.ts`), directly comparable to
 * `job.createdAt`. A phase never reached yet has no tick label at all, never a fabricated one. */
function phaseStartOffsets(events: StageEvent[], createdAtMs: number): Map<PipelinePhase, number> {
  const offsets = new Map<PipelinePhase, number>()
  for (const event of events) {
    if (event.kind !== 'transition' || event.edge !== 'start') continue
    if (!offsets.has(event.phase)) offsets.set(event.phase, event.at - createdAtMs)
  }
  return offsets
}

/** The clip track: a broadcast-timeline rail (not a row of numbered circles) with a sweeping
 * playhead at the leading edge of real progress and a timecode tick under each phase the run has
 * actually reached. This is the direction's signature interaction -- one continuous strip the eye
 * follows left to right, replacing six equal-weight stacked widgets. */
export function ClipTrack({
  currentPhase,
  completedPhases,
  phaseProgress,
  events,
  createdAt,
  segmentCount,
}: Props) {
  const activeIndex = currentPhase ? PHASE_ORDER.indexOf(currentPhase) : -1
  const offsets = phaseStartOffsets(events, new Date(createdAt).getTime())
  const segmentWidth = 100 / PHASE_ORDER.length
  const fillPct =
    activeIndex < 0
      ? 0
      : (activeIndex + (activeIndex === PHASE_ORDER.length - 1 ? 1 : (phaseProgress ?? 0))) *
        segmentWidth
  // T18L: a phase with real per-segment signal (voice/scenes/render) already advances fillPct
  // itself as segments complete -- its own ceiling is just its current fillPct, so the display
  // eases smoothly toward each new value rather than snapping. A phase with NO per-segment
  // signal (outline/budget/visuals, and the always-100 finalize case) has a flat fillPct for its
  // whole duration -- its ceiling is the START of the next phase, so the display creeps toward
  // it instead of sitting frozen, without ever visually entering the next phase's own territory.
  const ceilingPct =
    phaseProgress !== null
      ? fillPct
      : activeIndex < 0
        ? segmentWidth
        : Math.min(100, (activeIndex + 1) * segmentWidth)
  const smoothedFillPct = useSmoothProgress(fillPct, ceilingPct)

  return (
    <div className="flex flex-col gap-1.5">
      <div className="relative">
        <WaveScope seed={segmentCount} fillPct={smoothedFillPct} />
        {activeIndex >= 0 && (
          <div
            aria-hidden
            className="absolute top-1/2 flex -translate-y-1/2 flex-col items-center text-accent"
            style={{ left: `${Math.min(100, smoothedFillPct)}%`, marginLeft: -8 }}
          >
            <m.span
              animate={{ scale: [1, 1.3, 1], opacity: [0.6, 0, 0.6] }}
              transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
              className="absolute h-6 w-6 rounded-full bg-accent/40"
            />
            <IconPlayhead className="relative h-5 w-5 drop-shadow-[0_1px_2px_rgb(0_0_0_/_0.3)]" />
          </div>
        )}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {PHASE_ORDER.map((phase, i) => {
          const done = completedPhases.has(phase)
          const active = phase === currentPhase
          const offset = offsets.get(phase)
          return (
            <div key={phase} className="flex flex-col items-start gap-0.5">
              <span
                className={classNames(
                  'font-mono text-[10px] tabular-nums',
                  active ? 'text-accent-ink' : done ? 'text-ink-500' : 'text-ink-300',
                )}
              >
                {offset !== undefined ? formatTimecode(offset) : '--:--'}
              </span>
              <span
                className={classNames(
                  'hidden text-[10px] leading-tight sm:block',
                  active ? 'font-medium text-ink-900' : 'text-ink-500',
                )}
              >
                {PHASE_LABEL[phase]}
              </span>
              <span className="sm:hidden">{i === activeIndex ? PHASE_LABEL[phase] : null}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
