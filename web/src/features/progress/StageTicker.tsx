import { AnimatePresence, m } from 'motion/react'
import { IconCheck, IconDot } from '@/components/icons'
import type { StageEvent } from '@/domain/stage'

const VISIBLE = 3

function describeTransition(event: Extract<StageEvent, { kind: 'transition' }>): string {
  const segment = event.segmentTitle ? ` — ${event.segmentTitle}` : ''
  return `${event.label}${segment}`
}

/** The human-facing continuous readout of the real event stream -- `StageLog` (collapsed,
 * developer-facing, every raw event) doesn't give a passive viewer anything to watch; this does,
 * without inventing anything the backend didn't actually publish. */
export function StageTicker({ events }: { events: StageEvent[] }) {
  // Original array index, not node+edge+timestamp -- concurrent per-segment fan-out (T18B's own
  // design) regularly fires several segments' start/end for the same node in the same
  // millisecond, so `at` alone collides and produced a real React duplicate-key warning.
  const recent = events
    .map((event, arrayIndex) => ({ event, arrayIndex }))
    .filter(
      (e): e is { event: Extract<StageEvent, { kind: 'transition' }>; arrayIndex: number } =>
        e.event.kind === 'transition',
    )
    .slice(-VISIBLE)

  if (recent.length === 0) return null

  return (
    <div className="flex flex-col gap-1 overflow-hidden">
      <AnimatePresence initial={false}>
        {recent.map(({ event, arrayIndex }) => (
          <m.div
            key={arrayIndex}
            layout
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
            className="flex items-center gap-1.5 font-mono text-[11px] text-ink-500"
          >
            <span className="text-ink-300">
              {event.edge === 'end' ? <IconCheck className="h-3 w-3" /> : <IconDot className="h-3 w-3" />}
            </span>
            {describeTransition(event)}
          </m.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
