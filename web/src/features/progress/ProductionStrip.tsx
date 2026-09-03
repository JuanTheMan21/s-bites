import { m } from 'motion/react'
import { PHASE_LABEL, PHASE_ORDER, type PipelinePhase } from '@/domain/stage'
import { classNames } from '@/components/class-names'

interface Props {
  currentPhase: PipelinePhase | null
  completedPhases: Set<PipelinePhase>
  /** 0..1 within the active phase, or null when that phase has no per-segment signal
   * (`use-progress-model.ts::derivePhaseProgress`). Drives the rail fill between ticks. */
  phaseProgress: number | null
}

/** Not a spinner -- a row of phase ticks connected by a rail that fills as real progress
 * happens, with a sliding accent marker under the active one (`layoutId`-animated, so it glides
 * between phases instead of jumping) and a pulsing halo so the strip is never static even
 * during a long phase with no sub-progress signal of its own. */
export function ProductionStrip({ currentPhase, completedPhases, phaseProgress }: Props) {
  const activeIndex = currentPhase ? PHASE_ORDER.indexOf(currentPhase) : -1

  return (
    <div className="flex items-center">
      {PHASE_ORDER.map((phase, i) => {
        const done = completedPhases.has(phase)
        const active = phase === currentPhase
        return (
          <div key={phase} className="flex flex-1 items-center last:flex-initial">
            <div className="flex flex-col items-center gap-2">
              <div
                className={classNames(
                  'relative flex h-8 w-8 items-center justify-center rounded-full border font-mono text-xs transition-colors duration-(--duration-2)',
                  done && 'border-transparent bg-signal-ok text-paper-0',
                  active && !done && 'border-accent text-accent',
                  !done && !active && 'border-ink-300/40 text-ink-300',
                )}
              >
                {active && (
                  <m.span
                    aria-hidden
                    className="absolute inset-0 -z-10 rounded-full bg-accent/25"
                    animate={{ scale: [1, 1.6, 1], opacity: [0.5, 0, 0.5] }}
                    transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
                  />
                )}
                {done ? '✓' : i + 1}
                {active && (
                  <m.span
                    layoutId="production-strip-marker"
                    className="absolute inset-0 rounded-full border-2 border-accent"
                    transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
                  />
                )}
              </div>
              <span
                className={classNames(
                  'hidden text-center text-[10px] leading-tight sm:block',
                  active ? 'text-ink-900' : 'text-ink-500',
                )}
              >
                {PHASE_LABEL[phase]}
              </span>
            </div>
            {i < PHASE_ORDER.length - 1 && (
              <div className="mx-1 h-px flex-1 self-start bg-paper-2 mt-4">
                <m.div
                  className="h-full bg-signal-ok"
                  initial={false}
                  animate={{
                    width:
                      i < activeIndex
                        ? '100%'
                        : i === activeIndex
                          ? `${Math.round((phaseProgress ?? 0) * 100)}%`
                          : '0%',
                  }}
                  transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
