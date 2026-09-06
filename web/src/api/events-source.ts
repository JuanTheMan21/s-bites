import { artifactUrls } from './artifact-urls'

/** The server names every SSE message `stage` (never the default `message` event -- a listener
 * bound to `onmessage` would never fire, since the browser never dispatches that event name for
 * a named server-sent event). */
export const STAGE_EVENT_NAME = 'stage'

/** `withCredentials` is the whole reason `POST /auth/session` exists (T38A).
 *
 * `EventSource` cannot set request headers -- there is no API for it, in any browser -- so the
 * bearer token this app attaches to every other call is simply unavailable here. Sending the
 * `HttpOnly` session cookie instead is the only mechanism the platform offers, and this flag is
 * what makes the browser send it cross-origin at all.
 *
 * Worth knowing when debugging: a 401 on this endpoint does *not* surface as a readable error.
 * `EventSource` reports every failure as an opaque `error` event and then silently retries
 * forever, so an auth problem here looks exactly like a flaky network -- see the reconnect burst
 * detector in `features/progress/use-job-stream.ts`. */
export function openJobEventStream(jobId: string): EventSource {
  return new EventSource(artifactUrls.events(jobId), { withCredentials: true })
}
