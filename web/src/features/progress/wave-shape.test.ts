import { describe, expect, it } from 'vitest'
import { buildHarmonics, edgeEnvelope, sampleWave } from './wave-shape'

describe('buildHarmonics', () => {
  it('is deterministic for the same seed', () => {
    expect(buildHarmonics(5)).toEqual(buildHarmonics(5))
  })

  it('differs across seeds -- not a single hardcoded shape', () => {
    expect(buildHarmonics(5)).not.toEqual(buildHarmonics(9))
  })
})

describe('sampleWave', () => {
  it('stays within a sane bound regardless of x or t', () => {
    const harmonics = buildHarmonics(3)
    for (let i = 0; i <= 20; i++) {
      const value = sampleWave(harmonics, i / 20, i * 1.7)
      expect(value).toBeGreaterThanOrEqual(-1.0001)
      expect(value).toBeLessThanOrEqual(1.0001)
    }
  })

  it('evolves over time -- the whole point of replacing a frozen per-bar hash', () => {
    const harmonics = buildHarmonics(3)
    const early = sampleWave(harmonics, 0.4, 0)
    const later = sampleWave(harmonics, 0.4, 5)
    expect(early).not.toBeCloseTo(later, 5)
  })
})

describe('edgeEnvelope', () => {
  it('is zero at both edges and positive in the middle', () => {
    expect(edgeEnvelope(0)).toBeCloseTo(0)
    expect(edgeEnvelope(1)).toBeCloseTo(0)
    expect(edgeEnvelope(0.5)).toBeCloseTo(1)
  })

  it('clamps out-of-range input rather than producing a negative envelope', () => {
    expect(edgeEnvelope(-0.5)).toBeCloseTo(0)
    expect(edgeEnvelope(1.5)).toBeCloseTo(0)
  })
})
