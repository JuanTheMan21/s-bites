import { artifactUrls } from '@/domain/artifact-links'
import type { JobView } from '@/domain/job'

export function VideoPlayer({ job }: { job: JobView }) {
  if (!job.videoKey) return null
  return (
    // Range/206 support (api/byte_range.py) is what makes seeking on this element actually work
    // against local-disk storage, the primary day-to-day RUNTIME_ENV.
    //
    // crossOrigin="use-credentials" is load-bearing since T38A: a <video> element sends no
    // cookies cross-origin without it, and the session cookie is the only credential this
    // element can carry (there is no way to set a header on it). It also constrains the server,
    // which must answer with an exact Access-Control-Allow-Origin rather than "*" -- WEB_ORIGINS
    // already lists real origins, so that holds. The <track> below needs it for the same reason.
    <video
      controls
      crossOrigin="use-credentials"
      className="w-full rounded-xl border border-ink-300/25 bg-ink-900 shadow-(--shadow-2)"
      src={artifactUrls.video(job.jobId)}
    >
      {job.subtitlesKey && (
        <track kind="subtitles" src={artifactUrls.subtitles(job.jobId)} default />
      )}
    </video>
  )
}
