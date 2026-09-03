import { apiClient } from './client'
import { artifactUrls } from './artifact-urls'
import { ApiError } from './errors'
import type { components } from './schema'

export type VideoJobDto = components['schemas']['VideoJob']
export type SegmentDto = components['schemas']['Segment']
export type JobSubmissionDto = components['schemas']['JobSubmission']

/** `response.status` (not the schema-typed `error`) is what every caller here branches on --
 * FastAPI's real status codes (404, 409) are meaningful even when `app.openapi()` never declared
 * a `responses=` entry for them, and this is the one file allowed to know that. */
async function unwrap<T>(
  action: string,
  call: Promise<{ data?: T; response: Response }>,
): Promise<T> {
  const { data, response } = await call
  if (!response.ok) {
    let body: unknown
    try {
      body = await response.clone().json()
    } catch {
      body = null
    }
    throw new ApiError(action, response.status, body)
  }
  return data as T
}

export const listJobs = (): Promise<VideoJobDto[]> =>
  unwrap('list jobs', apiClient.GET('/jobs'))

export const submitJob = (body: JobSubmissionDto): Promise<VideoJobDto> =>
  unwrap('submit job', apiClient.POST('/jobs', { body }))

export const getJob = (jobId: string): Promise<VideoJobDto> =>
  unwrap('get job', apiClient.GET('/jobs/{job_id}', { params: { path: { job_id: jobId } } }))

export const resumeJob = (jobId: string): Promise<VideoJobDto> =>
  unwrap(
    'resume job',
    apiClient.POST('/jobs/{job_id}/resume', { params: { path: { job_id: jobId } } }),
  )

/** Not routed through `apiClient` -- `app.openapi()` has no meaningful schema for this route's
 * response (it declares `unknown`), so a plain `fetch` is exactly as typed as the generated
 * client would be, with less indirection. */
export async function getSegmentScene(jobId: string, index: number): Promise<unknown> {
  const response = await fetch(artifactUrls.segmentScene(jobId, index))
  if (!response.ok) {
    let body: unknown
    try {
      body = await response.clone().json()
    } catch {
      body = null
    }
    throw new ApiError('get segment scene', response.status, body)
  }
  return response.json()
}
