import type { SegmentView } from '@/domain/job'
import { SegmentCard } from '@/features/segments/SegmentCard'

/** The live-progress equivalent of a clip bin: segments scroll along one horizontal strip, the
 * way an NLE's project bin does, rather than wrapping into a dashboard card grid (the finish
 * review's own fidelity check named the grid a broken promise against the direction contract's
 * "segment blocks sit on that track, not a card grid"). `SegmentGrid` still owns the finished/
 * browse view in `JobResult` -- browsing many completed segments is a different task from
 * watching a strip fill in live, and a grid is the right tool for that one. */
export function ClipStrip({
  segments,
  activeSegmentIndex = null,
  onOpenSegment,
}: {
  segments: SegmentView[]
  activeSegmentIndex?: number | null
  onOpenSegment?: (index: number) => void
}) {
  if (segments.length === 0) return null
  return (
    <div className="relative -mx-1">
      <div className="flex snap-x snap-mandatory gap-3 overflow-x-auto px-1 pb-2">
        {segments.map((segment) => (
          <div key={segment.index} className="w-40 shrink-0 snap-start">
            <SegmentCard
              segment={segment}
              active={segment.index === activeSegmentIndex}
              onOpen={onOpenSegment}
            />
          </div>
        ))}
      </div>
      {/* Static scroll-affordance hint, not conditional on measured overflow -- a strip this
       * width regularly holds more segments than fit (6-21 per job), and a cheap always-on fade
       * beats a JS ResizeObserver for what is fundamentally a discoverability nudge. */}
      <div
        aria-hidden
        className="pointer-events-none absolute top-0 right-0 bottom-2 w-10 bg-gradient-to-l from-paper-1 to-transparent"
      />
    </div>
  )
}
