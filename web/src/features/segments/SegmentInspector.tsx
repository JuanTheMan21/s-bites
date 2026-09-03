import { Dialog } from '@/components/Dialog'
import { Skeleton } from '@/components/Skeleton'
import { TierBadge } from '@/components/TierBadge'
import { artifactUrls } from '@/domain/artifact-links'
import { describeIntent } from '@/domain/intent-label'
import type { SegmentView } from '@/domain/job'
import { SceneTree } from './SceneTree'
import { useSegmentSceneQuery } from './use-segment-scene'

interface Props {
  jobId: string
  segment: SegmentView | null
  onClose: () => void
}

export function SegmentInspector({ jobId, segment, onClose }: Props) {
  const scene = useSegmentSceneQuery(jobId, segment?.index ?? null)

  return (
    <Dialog open={segment !== null} onOpenChange={(open) => !open && onClose()} title={segment?.title ?? ''}>
      {segment && (
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-2">
            <TierBadge tier={segment.tier} />
            <span className="rounded-full bg-paper-2 px-2 py-0.5 font-mono text-[10px] text-ink-500 uppercase">
              {describeIntent(segment.visualIntent)}
            </span>
          </div>

          {segment.clipKey && (
            <video
              controls
              className="w-full rounded-md border border-ink-300/25 bg-ink-900"
              src={artifactUrls.segmentClip(jobId, segment.index)}
            />
          )}

          {segment.narration && (
            <div className="flex flex-col gap-1.5">
              <p className="font-mono text-xs tracking-wide text-ink-500 uppercase">Narration</p>
              <p className="font-sans text-sm leading-relaxed text-ink-700">{segment.narration}</p>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <p className="font-mono text-xs tracking-wide text-ink-500 uppercase">Composed scene</p>
            {scene.isPending && <Skeleton className="h-24" />}
            {scene.isError && (
              <p className="text-sm text-ink-500">Not composed yet.</p>
            )}
            {scene.data && <SceneTree tree={scene.data} />}
          </div>
        </div>
      )}
    </Dialog>
  )
}
