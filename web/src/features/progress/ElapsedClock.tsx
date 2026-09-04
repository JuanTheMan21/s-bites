import { useEffect, useState } from 'react'
import { IconPlay } from '@/components/icons'

function formatElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

/** One second of guaranteed, real motion per second, independent of whatever the backend is
 * doing -- a long silent stretch (a slow LLM call, a big render) never has to look like nothing
 * is happening, because this keeps ticking regardless. */
export function ElapsedClock({ startedAt }: { startedAt: string }) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])

  const elapsed = now - new Date(startedAt).getTime()

  return (
    <span
      className="inline-flex items-center gap-1 font-mono text-xs tabular-nums text-ink-500"
      aria-live="off"
    >
      <IconPlay className="h-3 w-3" />
      {formatElapsed(elapsed)}
    </span>
  )
}
