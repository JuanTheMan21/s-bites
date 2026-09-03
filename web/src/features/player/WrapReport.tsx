import { useEffect, useState } from 'react'
import { describeTier } from '@/domain/tier'
import type { JobView } from '@/domain/job'

const TIER_NUMBERS = [0, 1, 2]

function useCountUp(target: number, durationMs = 700): number {
  const [value, setValue] = useState(0)
  useEffect(() => {
    let frame: number
    const start = performance.now()
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / durationMs)
      setValue(Math.round(target * (1 - (1 - progress) ** 3)))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, durationMs])
  return value
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-display text-3xl text-ink-900 tabular-nums">{value}</span>
      <span className="font-mono text-[11px] tracking-wide text-ink-500 uppercase">{label}</span>
    </div>
  )
}

/** Only stats genuinely derivable from the job's own data -- no fabricated frame counts or
 * timings the frontend cannot actually measure. */
export function WrapReport({ job }: { job: JobView }) {
  const totalSeconds = job.segments.reduce((sum, s) => sum + (s.durationMs ?? 0), 0) / 1000
  const totalWords = job.segments.reduce(
    (sum, s) => sum + (s.narration ? s.narration.split(/\s+/).filter(Boolean).length : 0),
    0,
  )
  const segmentCount = useCountUp(job.segments.length)
  const seconds = useCountUp(Math.round(totalSeconds))
  const words = useCountUp(totalWords)

  const tierCounts = TIER_NUMBERS.map(
    (tier) => job.segments.filter((s) => s.tier === tier).length,
  )
  const total = tierCounts.reduce((a, b) => a + b, 0) || 1

  return (
    <div className="flex flex-col gap-5 rounded-lg border border-ink-300/25 bg-paper-1 p-5">
      <p className="font-mono text-xs tracking-wide text-ink-500 uppercase">Wrap report</p>
      <div className="grid grid-cols-3 gap-4">
        <Stat label="Segments" value={segmentCount} />
        <Stat label="Runtime (s)" value={seconds} />
        <Stat label="Words narrated" value={words} />
      </div>
      <div className="flex flex-col gap-2">
        <p className="font-mono text-[11px] tracking-wide text-ink-500 uppercase">Tier mix</p>
        <div className="flex h-2 overflow-hidden rounded-full bg-paper-2">
          {TIER_NUMBERS.map((tier, i) => {
            const descriptor = describeTier(tier)!
            const pct = (tierCounts[i]! / total) * 100
            if (pct === 0) return null
            return (
              <div
                key={tier}
                style={{ width: `${pct}%`, background: `var(${descriptor.colorVar})` }}
              />
            )
          })}
        </div>
        <div className="flex gap-4 font-mono text-[11px] text-ink-500">
          {TIER_NUMBERS.map((tier, i) => (
            <span key={tier}>
              {describeTier(tier)!.label}: {tierCounts[i]}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
