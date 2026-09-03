import { describe, expect, it } from 'vitest'
import { ApiError } from '@/adapters/job-adapter'
import { describeSubmitError } from './submit-error'

describe('describeSubmitError', () => {
  it('gives the queue-stub 500 case its own honest, specific message', () => {
    const message = describeSubmitError(new ApiError('submit job', 500, null))
    expect(message).toContain('job queue')
    expect(message).toContain('Nothing was charged')
  })

  it('gives 422 a rewording hint', () => {
    expect(describeSubmitError(new ApiError('submit job', 422, null))).toContain('rewording')
  })

  it('falls back to a generic HTTP message for other ApiError statuses', () => {
    expect(describeSubmitError(new ApiError('submit job', 403, null))).toContain('403')
  })

  it('reports a reachability problem for a non-ApiError failure', () => {
    expect(describeSubmitError(new TypeError('Failed to fetch'))).toContain('reach the backend')
  })
})
