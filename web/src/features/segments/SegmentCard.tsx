import { m } from 'motion/react'
import { TierBadge } from '@/components/TierBadge'
import { describeIntent } from '@/domain/intent-label'
import type { SegmentView } from '@/domain/job'

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  return `${(ms / 1000).toFixed(1)}s`
}

export function SegmentCard({
  segment,
  onOpen,
}: {
  segment: SegmentView
  onOpen?: (index: number) => void
}) {
  return (
    <m.button
      layout
      onClick={onOpen ? () => onOpen(segment.index) : undefined}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
      className="group flex flex-col gap-2.5 rounded-lg border border-ink-300/25 bg-paper-1 p-4 text-left shadow-(--shadow-1) transition-[transform,box-shadow] duration-(--duration-1) ease-(--ease-expo-out) hover:-translate-y-0.5 hover:shadow-(--shadow-2) disabled:cursor-default"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-mono text-[11px] text-ink-500">
          {String(segment.index + 1).padStart(2, '0')}
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
        <span className="font-mono text-[11px] text-ink-500">{formatDuration(segment.durationMs)}</span>
      </div>
    </m.button>
  )
}
