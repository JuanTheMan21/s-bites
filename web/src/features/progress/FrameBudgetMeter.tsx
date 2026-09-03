import { m } from 'motion/react'
import { describeTier } from '@/domain/tier'
import type { SegmentView } from '@/domain/job'

/** Not decoration -- the frame budget is a real, load-bearing number in this pipeline
 * (`FRAME_BUDGET` in `.env.example`), and this is tiers actually filling in as they're assigned,
 * segment by segment, in real time. */
export function FrameBudgetMeter({ segments }: { segments: SegmentView[] }) {
  if (segments.length === 0) return null
  const assigned = segments.filter((s) => s.tier !== null).length

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between font-mono text-[11px] text-ink-500 uppercase">
        <span>Tier assignment</span>
        <span>
          {assigned}/{segments.length}
        </span>
      </div>
      <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full bg-paper-2">
        {segments.map((segment) => {
          const descriptor = describeTier(segment.tier)
          return (
            <m.div
              key={segment.index}
              className="h-full flex-1 rounded-full"
              initial={{ opacity: 0 }}
              animate={{
                opacity: 1,
                backgroundColor: descriptor ? `var(${descriptor.colorVar})` : 'transparent',
              }}
              transition={{ duration: 0.3 }}
            />
          )
        })}
      </div>
    </div>
  )
}
