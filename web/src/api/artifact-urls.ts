import { API_BASE_URL } from './base-url'

/** URL builders for every artifact route -- none of these are fetched with JS (their responses
 * aren't JSON), so they are consumed directly as `<video src>`, `<a href>`, or `<img src>`
 * targets rather than going through `openapi-fetch`. */
export const artifactUrls = {
  video: (jobId: string) => `${API_BASE_URL}/jobs/${jobId}/video`,
  subtitles: (jobId: string) => `${API_BASE_URL}/jobs/${jobId}/subtitles`,
  scorm: (jobId: string) => `${API_BASE_URL}/jobs/${jobId}/scorm`,
  segmentAudio: (jobId: string, index: number) =>
    `${API_BASE_URL}/jobs/${jobId}/segments/${index}/audio`,
  segmentClip: (jobId: string, index: number) =>
    `${API_BASE_URL}/jobs/${jobId}/segments/${index}/clip`,
  segmentScene: (jobId: string, index: number) =>
    `${API_BASE_URL}/jobs/${jobId}/segments/${index}/scene`,
  events: (jobId: string) => `${API_BASE_URL}/jobs/${jobId}/events`,
}
