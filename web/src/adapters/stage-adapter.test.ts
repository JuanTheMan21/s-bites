import { describe, expect, it } from 'vitest'
import { toStageEvent } from './stage-adapter'

describe('toStageEvent', () => {
  it('parses a transition with a recognised node into its phase', () => {
    const event = toStageEvent({ node: 'render_scene', stage: 'start', segment_index: 2 }, 100)
    expect(event).toEqual({
      kind: 'transition',
      node: 'render_scene',
      phase: 'render',
      label: 'Rendering',
      edge: 'start',
      segmentIndex: 2,
      segmentTitle: undefined,
      at: 100,
    })
  })

  it('degrades an unrecognised node to a titlecased unknown phase, not a crash', () => {
    const event = toStageEvent({ node: 'summarize_findings', stage: 'end' }, 1)
    expect(event.kind).toBe('transition')
    if (event.kind === 'transition') {
      expect(event.phase).toBe('unknown')
      expect(event.label).toBe('Summarize Findings')
    }
  })

  it('parses a terminal status event', () => {
    const event = toStageEvent({ job_status: 'succeeded', terminal: true }, 5)
    expect(event).toEqual({ kind: 'status', status: 'succeeded', terminal: true, at: 5 })
  })

  it('parses a retryable failure as non-terminal', () => {
    const event = toStageEvent({ job_status: 'failed', terminal: false }, 5)
    expect(event).toEqual({ kind: 'status', status: 'failed', terminal: false, at: 5 })
  })

  it('defaults a missing terminal flag to true rather than hanging open', () => {
    const event = toStageEvent({ job_status: 'succeeded' }, 5)
    expect(event).toEqual({ kind: 'status', status: 'succeeded', terminal: true, at: 5 })
  })

  it('never throws on malformed JSON, arrays, or primitives', () => {
    for (const raw of [null, undefined, 'plain string', 42, [1, 2, 3], {}]) {
      expect(() => toStageEvent(raw)).not.toThrow()
      expect(toStageEvent(raw).kind).toBe('unknown')
    }
  })
})
