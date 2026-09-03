import { describe, expect, it } from 'vitest'
import { deriveCompletedPhases } from './stage'

describe('deriveCompletedPhases', () => {
  it('reports nothing done before any segment exists', () => {
    expect(deriveCompletedPhases([])).toEqual(new Set())
  })

  it('marks outline done as soon as segments exist', () => {
    const done = deriveCompletedPhases([{ durationMs: null, tier: null, hasScene: false }])
    expect(done.has('outline')).toBe(true)
    expect(done.has('voice')).toBe(false)
  })

  it('marks voice done only once every segment has a measured duration', () => {
    const partial = deriveCompletedPhases([
      { durationMs: 1000, tier: null, hasScene: false },
      { durationMs: null, tier: null, hasScene: false },
    ])
    expect(partial.has('voice')).toBe(false)

    const complete = deriveCompletedPhases([
      { durationMs: 1000, tier: null, hasScene: false },
      { durationMs: 2000, tier: null, hasScene: false },
    ])
    expect(complete.has('voice')).toBe(true)
  })

  it('marks budget and visuals done together once every segment has a tier', () => {
    const done = deriveCompletedPhases([{ durationMs: 1000, tier: 1, hasScene: false }])
    expect(done.has('budget')).toBe(true)
    expect(done.has('visuals')).toBe(true)
  })

  it('marks scenes done once every segment has a composed scene', () => {
    const done = deriveCompletedPhases([{ durationMs: 1000, tier: 1, hasScene: true }])
    expect(done.has('scenes')).toBe(true)
  })

  it('backfills a job refreshed mid-run into the correct partial state', () => {
    const done = deriveCompletedPhases([
      { durationMs: 1000, tier: 2, hasScene: true },
      { durationMs: 1200, tier: null, hasScene: false },
    ])
    expect([...done].sort()).toEqual(['outline', 'voice'])
  })
})
