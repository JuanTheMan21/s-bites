import { describe, expect, it } from 'vitest'
import { nextProgressValue } from './use-smooth-progress'

describe('nextProgressValue', () => {
  it('eases up toward a real target that jumped ahead of the current display', () => {
    const next = nextProgressValue(10, 40, 40, 0.1)
    expect(next).toBeGreaterThan(10)
    expect(next).toBeLessThan(40)
  })

  it('creeps toward the ceiling when the target has not moved', () => {
    const next = nextProgressValue(10, 10, 30, 0.1)
    expect(next).toBeGreaterThan(10)
    expect(next).toBeLessThan(30)
  })

  it('never exceeds the ceiling even after many ticks', () => {
    let value = 0
    for (let i = 0; i < 10_000; i++) {
      value = nextProgressValue(value, 0, 20, 0.05)
    }
    expect(value).toBeLessThanOrEqual(20)
    expect(value).toBeGreaterThan(19) // asymptotically close, never claims more
  })

  it('never regresses once a real target has been reached', () => {
    const atCeiling = nextProgressValue(19.9, 0, 20, 100) // one huge tick to approach the ceiling
    const next = nextProgressValue(atCeiling, 0, 20, 0.1)
    expect(next).toBeGreaterThanOrEqual(atCeiling - 1e-9)
  })

  it('lets a real target win even when it is below the current creep position', () => {
    // display has crept ahead within the current phase's headroom; a fresh, lower-than-creep
    // target should not pull display backward (targets are monotonic non-decreasing upstream).
    const next = nextProgressValue(15, 12, 20, 0.1)
    expect(next).toBeGreaterThanOrEqual(15)
  })

  it('handles a ceiling that is somehow below the target without going negative or NaN', () => {
    const next = nextProgressValue(5, 10, 8, 0.1)
    expect(Number.isFinite(next)).toBe(true)
    expect(next).toBeGreaterThanOrEqual(5)
  })
})
