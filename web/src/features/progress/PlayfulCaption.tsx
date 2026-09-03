import { AnimatePresence, m } from 'motion/react'
import { useEffect, useState } from 'react'
import { PHASE_LABEL, type PipelinePhase } from '@/domain/stage'
import { PHASE_COPY } from './phase-copy'

const ROTATE_MS = 3500
const PIN_AFTER_MS = 90000

/** The real stage label (`PHASE_LABEL`) is always rendered alongside the rotating line, never
 * replaced by it -- and past 90s in one phase the copy pins to a factual line, since playful
 * copy during a genuinely long wait reads as mockery rather than personality.
 *
 * The caller keys this component by `phase` (`LiveProgress.tsx`) so a phase change remounts it
 * fresh: every piece of state here -- including "when did this phase start" -- resets via a
 * lazy `useState` initializer, the one place React allows an impure `Date.now()` read, rather
 * than a reset-effect or a value computed during render. */
export function PlayfulCaption({ phase }: { phase: PipelinePhase }) {
  const lines = PHASE_COPY[phase]
  const [index, setIndex] = useState(0)
  const [pinned, setPinned] = useState(false)
  const [startedAt] = useState(() => Date.now())

  useEffect(() => {
    const timer = setInterval(() => {
      const elapsed = Date.now() - startedAt
      if (elapsed >= PIN_AFTER_MS) {
        setPinned(true)
        return
      }
      setIndex((i) => (i + 1) % lines.length)
    }, ROTATE_MS)
    return () => clearInterval(timer)
  }, [lines.length, startedAt])

  const caption = pinned ? `Still ${PHASE_LABEL[phase].toLowerCase()}…` : lines[index]

  return (
    <div className="flex flex-col gap-0.5">
      <p className="font-mono text-xs tracking-wide text-ink-500 uppercase">{PHASE_LABEL[phase]}</p>
      <AnimatePresence mode="wait">
        <m.p
          key={caption}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          className="font-display text-lg text-ink-900"
        >
          {caption}
        </m.p>
      </AnimatePresence>
    </div>
  )
}
