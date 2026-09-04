import { artifactUrls } from '@/domain/artifact-links'
import type { JobView } from '@/domain/job'

export function VideoPlayer({ job }: { job: JobView }) {
  if (!job.videoKey) return null
  return (
    // Range/206 support (api/byte_range.py) is what makes seeking on this element actually work
    // against local-disk storage, the primary day-to-day RUNTIME_ENV.
    <video
      controls
      className="w-full rounded-xl border border-ink-300/25 bg-ink-900 shadow-(--shadow-2)"
      src={artifactUrls.video(job.jobId)}
    >
      {job.subtitlesKey && (
        <track kind="subtitles" src={artifactUrls.subtitles(job.jobId)} default />
      )}
    </video>
  )
}
