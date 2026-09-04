import { AnimatePresence, m } from 'motion/react'
import { useEffect, useState } from 'react'
import { PHASE_LABEL, type PipelinePhase } from '@/domain/stage'
import { LONG_WAIT_COPY, PHASE_COPY } from './phase-copy'

const ROTATE_MS = 3500
const PIN_AFTER_MS = 90000

/** The real stage label (`PHASE_LABEL`) is always rendered alongside the rotating line, never
 * replaced by it -- and past 90s in one phase the copy switches to `LONG_WAIT_COPY` (still
 * rotating, just factual) rather than continuing to joke, since playful copy during a genuinely
 * long wait reads as mockery rather than personality.
 *
 * The caller keys this component by `phase` (`LiveProgress.tsx`) so a phase change remounts it
 * fresh: every piece of state here -- including "when did this phase start" -- resets via a
 * lazy `useState` initializer, the one place React allows an impure `Date.now()` read, rather
 * than a reset-effect or a value computed during render. */
export function PlayfulCaption({ phase }: { phase: PipelinePhase }) {
  const [index, setIndex] = useState(0)
  const [pinned, setPinned] = useState(false)
  const [startedAt] = useState(() => Date.now())

  const lines = pinned ? LONG_WAIT_COPY[phase] : PHASE_COPY[phase]

  useEffect(() => {
    const timer = setInterval(() => {
      const elapsed = Date.now() - startedAt
      if (elapsed >= PIN_AFTER_MS && !pinned) {
        setPinned(true)
        setIndex(0)
        return
      }
      setIndex((i) => (i + 1) % lines.length)
    }, ROTATE_MS)
    return () => clearInterval(timer)
  }, [lines.length, startedAt, pinned])

  const caption = lines[index]

  return (
    <div className="flex min-w-0 items-baseline gap-2.5">
      <span className="inline-flex shrink-0 items-center gap-1.5 font-mono text-[11px] font-medium tracking-wide text-accent-ink uppercase">
        <m.span
          aria-hidden
          className="h-1.5 w-1.5 rounded-full bg-accent"
          animate={{ opacity: [1, 0.35, 1] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
        />
        Rec
      </span>
      <span className="shrink-0 font-mono text-[11px] text-ink-500 uppercase">
        {PHASE_LABEL[phase]}
      </span>
      <AnimatePresence mode="wait">
        <m.p
          key={caption}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          className="min-w-0 flex-1 truncate font-display text-base text-ink-900"
        >
          {caption}
        </m.p>
      </AnimatePresence>
    </div>
  )
}
