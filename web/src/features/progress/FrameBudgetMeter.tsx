import { m } from 'motion/react'
import { describeTier } from '@/domain/tier'
import type { SegmentView } from '@/domain/job'

/** Not decoration -- the frame budget is a real, load-bearing number in this pipeline
 * (`FRAME_BUDGET` in `.env.example`), and this is tiers actually filling in as they're assigned,
 * segment by segment, in real time. Renders a placeholder track even before segments exist
 * (rather than nothing) -- the meter used to be simply absent for the whole first stretch of a
 * run, exactly the part that most needed something visibly alive. */
export function FrameBudgetMeter({ segments }: { segments: SegmentView[] }) {
  const assigned = segments.filter((s) => s.tier !== null).length

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between font-mono text-[11px] text-ink-500 uppercase">
        <span>Tier assignment</span>
        <span>{segments.length > 0 ? `${assigned}/${segments.length}` : '—'}</span>
      </div>
      <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full bg-paper-2">
        {segments.length === 0 ? (
          <m.div
            className="h-full w-full rounded-full"
            style={{
              background:
                'linear-gradient(90deg, transparent, var(--color-ink-300), transparent)',
              backgroundSize: '50% 100%',
            }}
            animate={{ backgroundPositionX: ['-50%', '150%'] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'linear' }}
          />
        ) : (
          segments.map((segment) => {
            const descriptor = describeTier(segment.tier)
            return (
              <m.div
                key={segment.index}
                className="relative h-full flex-1 overflow-hidden rounded-full"
                initial={{ opacity: 0 }}
                animate={{
                  opacity: 1,
                  backgroundColor: descriptor ? `var(${descriptor.colorVar})` : 'var(--color-paper-2)',
                }}
                transition={{ duration: 0.3 }}
              >
                {!descriptor && (
                  <m.div
                    className="absolute inset-0"
                    style={{
                      background:
                        'linear-gradient(90deg, transparent, var(--color-ink-300), transparent)',
                      backgroundSize: '200% 100%',
                    }}
                    animate={{ backgroundPositionX: ['-100%', '200%'] }}
                    transition={{ duration: 1.4, repeat: Infinity, ease: 'linear' }}
                  />
                )}
              </m.div>
            )
          })
        )}
      </div>
    </div>
  )
}
