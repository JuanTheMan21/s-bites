import { m } from 'motion/react'
import { TierBadge } from '@/components/TierBadge'
import { classNames } from '@/components/class-names'
import { describeIntent } from '@/domain/intent-label'
import type { SegmentView } from '@/domain/job'
import { describeTier } from '@/domain/tier'

function formatDuration(ms: number | null): string {
  if (ms === null) return '--:--'
  const totalTenths = Math.round(ms / 100)
  const minutes = Math.floor(totalTenths / 600)
  const seconds = (totalTenths % 600) / 10
  return `${minutes}:${seconds.toFixed(1).padStart(4, '0')}`
}

/** A clip block on the segment track, not a generic dashboard card: the top edge carries the
 * segment's real tier as a literal fill color (the `domain/tier.ts` bug used to make this
 * colorless), and every number is a timecode, not a label. */
export function SegmentCard({
  segment,
  active = false,
  onOpen,
}: {
  segment: SegmentView
  active?: boolean
  onOpen?: (index: number) => void
}) {
  const descriptor = describeTier(segment.tier)

  return (
    <m.button
      layout
      onClick={onOpen ? () => onOpen(segment.index) : undefined}
      initial={{ opacity: 0, y: 10 }}
      animate={{
        opacity: 1,
        y: 0,
        boxShadow: active
          ? '0 0 0 1px var(--color-accent), 0 6px 20px -6px var(--color-accent)'
          : 'var(--shadow-1)',
      }}
      transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
      className={classNames(
        'group flex flex-col overflow-hidden rounded-lg border text-left transition-[transform] duration-(--duration-1) ease-(--ease-expo-out) hover:-translate-y-0.5 disabled:cursor-default',
        active ? 'border-accent bg-accent-tint' : 'border-ink-300/25 bg-paper-1',
      )}
    >
      <span
        aria-hidden
        className="h-1.5 w-full transition-colors duration-(--duration-2)"
        style={{ background: descriptor ? `var(${descriptor.colorVar})` : 'var(--color-paper-2)' }}
      />
      <div className="flex flex-col gap-2.5 p-4">
        <div className="flex items-start justify-between gap-2">
          <span className="flex items-center gap-1.5 font-mono text-[11px] text-ink-500">
            {String(segment.index + 1).padStart(2, '0')}
            {active && (
              <m.span
                aria-hidden
                className="h-1.5 w-1.5 rounded-full bg-accent"
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
              />
            )}
          </span>
          <TierBadge tier={segment.tier} />
        </div>
        <p className="font-display text-base leading-snug text-ink-900 line-clamp-2">
          {segment.title}
        </p>
        <div className="mt-auto flex items-center justify-between gap-2 pt-1">
          <span className="rounded-full bg-paper-2 px-2 py-0.5 font-mono text-[10px] text-ink-500 uppercase">
            {describeIntent(segment.visualIntent)}
          </span>
          <span className="font-mono text-[11px] text-ink-500 tabular-nums">
            {formatDuration(segment.durationMs)}
          </span>
        </div>
      </div>
    </m.button>
  )
}
