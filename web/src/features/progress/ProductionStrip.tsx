import { m } from 'motion/react'
import { PHASE_LABEL, PHASE_ORDER, type PipelinePhase } from '@/domain/stage'
import { classNames } from '@/components/class-names'

interface Props {
  currentPhase: PipelinePhase | null
  completedPhases: Set<PipelinePhase>
}

/** Not a spinner -- a row of phase ticks with a sliding accent marker under the active one,
 * `layoutId`-animated so it glides between phases instead of jumping. This is the "moving parts,
 * not a stale still page" answer for the progress view's header. */
export function ProductionStrip({ currentPhase, completedPhases }: Props) {
  return (
    <div className="flex items-center gap-1">
      {PHASE_ORDER.map((phase) => {
        const done = completedPhases.has(phase)
        const active = phase === currentPhase
        return (
          <div key={phase} className="flex flex-1 flex-col items-center gap-2">
            <div
              className={classNames(
                'relative flex h-8 w-8 items-center justify-center rounded-full border font-mono text-xs transition-colors duration-(--duration-2)',
                done && 'border-transparent bg-signal-ok text-paper-0',
                active && !done && 'border-accent text-accent',
                !done && !active && 'border-ink-300/40 text-ink-300',
              )}
            >
              {done ? '✓' : PHASE_ORDER.indexOf(phase) + 1}
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
        )
      })}
    </div>
  )
}
