import { artifactUrls } from './artifact-urls'

/** The server names every SSE message `stage` (never the default `message` event -- a listener
 * bound to `onmessage` would never fire, since the browser never dispatches that event name for
 * a named server-sent event). */
export const STAGE_EVENT_NAME = 'stage'

export function openJobEventStream(jobId: string): EventSource {
  return new EventSource(artifactUrls.events(jobId))
}
