import type { SegmentView } from '@/domain/job'
import { SegmentCard } from './SegmentCard'

export function SegmentGrid({
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
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {segments.map((segment) => (
        <SegmentCard
          key={segment.index}
          segment={segment}
          active={segment.index === activeSegmentIndex}
          onOpen={onOpenSegment}
        />
      ))}
    </div>
  )
}
