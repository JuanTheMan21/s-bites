import type { JobView } from '@/domain/job'
import { ArtifactActions } from '@/features/player/ArtifactActions'
import { VideoPlayer } from '@/features/player/VideoPlayer'
import { WrapReport } from '@/features/player/WrapReport'
import { SegmentGrid } from '@/features/segments/SegmentGrid'

export function JobResult({
  job,
  onOpenSegment,
}: {
  job: JobView
  onOpenSegment: (index: number) => void
}) {
  return (
    <div className="flex flex-col gap-6">
      <VideoPlayer job={job} />
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-ink-500">
          Any segment's clip and composed scene can be inspected individually below.
        </p>
        <ArtifactActions job={job} />
      </div>
      <WrapReport job={job} />
      <SegmentGrid segments={job.segments} onOpenSegment={onOpenSegment} />
    </div>
  )
}
