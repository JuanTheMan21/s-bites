import type { SegmentView } from '@/domain/job'
import { SegmentCard } from './SegmentCard'

export function SegmentGrid({
  segments,
  onOpenSegment,
}: {
  segments: SegmentView[]
  onOpenSegment?: (index: number) => void
}) {
  if (segments.length === 0) return null
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {segments.map((segment) => (
        <SegmentCard key={segment.index} segment={segment} onOpen={onOpenSegment} />
      ))}
    </div>
  )
}
