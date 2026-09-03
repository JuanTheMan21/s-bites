import { getJob, listJobs, resumeJob, submitJob } from '@/api/endpoints'
import type { SegmentDto, VideoJobDto } from '@/api/endpoints'
import type { JobView, SegmentView } from '@/domain/job'

export { ApiError } from '@/api/errors'

/** The tripwire for "contracts cannot silently diverge" (T24's own DoD): every field is read by
 * explicit destructure, never a spread. A field the backend renames or removes fails `tsc` right
 * here, and nowhere else has to know or care. */
export function toJobView(dto: VideoJobDto): JobView {
  const {
    job_id,
    topic,
    target_duration_ms,
    status,
    created_at,
    segments,
    video_key,
    subtitles_key,
    error,
  } = dto
  return {
    jobId: job_id,
    topic,
    targetDurationMs: target_duration_ms,
    status,
    createdAt: created_at ?? new Date(0).toISOString(),
    segments: (segments ?? []).map(toSegmentView),
    videoKey: video_key ?? null,
    subtitlesKey: subtitles_key ?? null,
    error: error ?? null,
  }
}

export async function fetchJobList(): Promise<JobView[]> {
  return (await listJobs()).map(toJobView)
}

export async function fetchJob(jobId: string): Promise<JobView> {
  return toJobView(await getJob(jobId))
}

export async function createJob(input: { topic: string; targetDurationMs: number }): Promise<JobView> {
  return toJobView(await submitJob({ topic: input.topic, target_duration_ms: input.targetDurationMs }))
}

export async function resumeJobRequest(jobId: string): Promise<JobView> {
  return toJobView(await resumeJob(jobId))
}

function toSegmentView(dto: SegmentDto): SegmentView {
  const { index, title, summary, visual_intent, importance, narration, duration_ms, tier, scene, clip_key } =
    dto
  return {
    index,
    title,
    summary,
    visualIntent: visual_intent,
    importance,
    narration: narration ?? null,
    durationMs: duration_ms ?? null,
    tier: tier ?? null,
    hasScene: scene != null,
    clipKey: clip_key ?? null,
  }
}
