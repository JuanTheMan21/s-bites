/**
 * Frontend-owned view models for a job and its segments -- what every component outside
 * `api/`/`adapters/` is allowed to depend on (enforced by `eslint.config.js`'s
 * `no-restricted-imports`). This file is also the classification of which backend fields are
 * STABLE (safe to bind a component to) vs VOLATILE (T18 churns these routinely).
 *
 * STABLE: job_id, topic, target_duration_ms, status, created_at, video_key, subtitles_key,
 *         error; JobStatus (4 members); Segment's scalar fields (index, title, summary,
 *         duration_ms, narration, clip_key). Removing one of these is a real contract break and
 *         fails `tsc` in `adapters/job-adapter.ts`, the one file that destructures them.
 * SEMI-STABLE (must degrade, never crash): the graph's stage node names (`domain/stage.ts`);
 *         Segment.tier (0/1/2, `domain/tier.ts`); Segment.importance (1-5); RenderOutcome
 *         (`degraded_segments`, T18I) -- a segment with no entry rendered clean, by design
 *         (`core/render_outcome.py`'s own docstring), so absence is data, not a gap.
 * VOLATILE: VisualIntent -- the `/newintent` command exists specifically to add members
 *         (`domain/intent-label.ts` widens it to `string` and labels with a fallback).
 * MAXIMALLY VOLATILE: Segment.scene -- `dict[str, Any]` on the backend, shape varies per
 *         layout/block choice, changes every T18 iteration. Never typed here; rendered as a
 *         generic tree by `adapters/scene-adapter.ts` + the scene inspector instead.
 */

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed'

/** One segment's own render history -- present only when it needed more than a clean first
 * attempt (T18K, D164's own reasoning: absence already says "rendered clean"). */
export interface DegradedSegmentView {
  segmentIndex: number
  attempts: number
  findingCodes: string[]
  reauthored: boolean
  fallbackUsed: boolean
  originalTier: number
}

export interface SegmentView {
  index: number
  title: string
  summary: string
  /** Widened from the backend's closed enum -- see `domain/intent-label.ts`. */
  visualIntent: string
  importance: number
  narration: string | null
  durationMs: number | null
  tier: number | null
  /** Whether this segment's composed scene exists yet -- never the scene payload itself. */
  hasScene: boolean
  clipKey: string | null
  /** `null` for the common case (this segment rendered clean on its first attempt). Only ever
   * populated once the job reaches `finalize` -- absent throughout the live run itself, not a
   * live per-attempt signal (`core/graph/nodes/finalize.py`'s `degraded` list comprehension). */
  degraded: DegradedSegmentView | null
}

export interface JobView {
  jobId: string
  topic: string
  targetDurationMs: number
  status: JobStatus
  createdAt: string
  segments: SegmentView[]
  videoKey: string | null
  subtitlesKey: string | null
  error: string | null
}
