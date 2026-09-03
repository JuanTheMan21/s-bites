import { ApiError } from '@/adapters/job-adapter'

/** Maps a submission failure to copy a user can act on. The 500 case is the one that actually
 * happened in production (config.py's QUEUE_ENV bridge closes the underlying cause, but a
 * future real Service Bus outage post-T34 reproduces the same shape) -- it gets an honest,
 * specific line rather than a generic "something went wrong". */
export function describeSubmitError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) return "That topic wasn't accepted. Try rewording it."
    if (error.status >= 500) {
      return "The backend couldn't start this job — its job queue may not be running. Nothing was charged; try again."
    }
    return `We couldn't start this job (HTTP ${error.status}).`
  }
  return "Couldn't reach the backend. Check it's running and try again."
}
