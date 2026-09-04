import { useEffect, useState } from 'react'

const EXAMPLES = [
  'Teach me about SQL injection',
  'What are GitHub Actions?',
  'Explain how OAuth works',
  'How does DNS resolution work?',
]

const TYPE_MS = 45
const DELETE_MS = 25
const PAUSE_MS = 1400
const GAP_MS = 350

/** A typewriter cycle through example topics for the composer's placeholder -- purely cosmetic
 * copy, not real data, so it lives here rather than anywhere near `phase-copy.ts`'s real-progress
 * rule (D137). `active` should be `false` once the visitor has typed something: the native
 * `placeholder` attribute is already invisible whenever the field has a value, so this only
 * needs to stop ticking to avoid wasted timers, not to hide anything. */
export function usePlaceholderCycle(active: boolean): string {
  const [text, setText] = useState('')
  const [exampleIndex, setExampleIndex] = useState(0)

  useEffect(() => {
    if (!active) return
    let cancelled = false
    let charIndex = 0
    let timer: ReturnType<typeof setTimeout>
    const full = EXAMPLES[exampleIndex % EXAMPLES.length]!

    function typeNext() {
      if (cancelled) return
      if (charIndex <= full.length) {
        setText(full.slice(0, charIndex))
        charIndex += 1
        timer = setTimeout(typeNext, TYPE_MS)
      } else {
        timer = setTimeout(deleteNext, PAUSE_MS)
      }
    }

    function deleteNext() {
      if (cancelled) return
      if (charIndex > 0) {
        charIndex -= 1
        setText(full.slice(0, charIndex))
        timer = setTimeout(deleteNext, DELETE_MS)
      } else {
        timer = setTimeout(() => {
          if (!cancelled) setExampleIndex((i) => (i + 1) % EXAMPLES.length)
        }, GAP_MS)
      }
    }

    typeNext()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [active, exampleIndex])

  return text
}
