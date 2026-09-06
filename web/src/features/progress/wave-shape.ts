/** Pure wave math -- no DOM, no React. `WaveScope.tsx` samples this every frame; this module
 * only knows how to answer "what's the wave's shape at this seed, this x, this time".
 *
 * T18L: replaces `ClipTrack.tsx`'s old `barHeightPct(i)` -- a frozen-for-the-job's-whole-life
 * per-bar hash with no time dimension at all, which is what made the old track "move only in
 * big bits" (the only motion was a colour swap driven by phase changes). A sum of a few
 * sine harmonics at different frequencies/phases/speeds reads as one continuous flowing curve
 * instead of independent static bars, and evolves continuously with `t` so it never sits still.
 */

const HARMONIC_COUNT = 4

export interface Harmonic {
  freq: number
  amp: number
  phase: number
  speed: number
}

/** A cheap deterministic pseudo-random hash -- same family as the old `barHeightPct`'s sine
 * hash, now used to seed harmonic parameters rather than a frozen per-bar height. */
function hash(n: number): number {
  const x = Math.sin(n * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

/** Deterministic from `segmentCount` alone, matching the old bar track's own determinism
 * contract (D137: "the same job renders the same waveform on every re-render/remount") --
 * that contract was already keyed on segment count, not a job id, so this preserves it exactly
 * rather than widening it. */
export function buildHarmonics(seed: number): Harmonic[] {
  return Array.from({ length: HARMONIC_COUNT }, (_, i) => {
    const h1 = hash(seed + i * 7.1 + 1)
    const h2 = hash(seed + i * 13.7 + 2)
    const h3 = hash(seed + i * 19.3 + 3)
    return {
      freq: 1.5 + i * 1.3 + h1 * 0.6,
      amp: (0.55 + h2 * 0.45) / (i + 1),
      phase: h3 * Math.PI * 2,
      speed: 0.35 + h1 * 0.45,
    }
  })
}

/** The wave's raw oscillation at horizontal position `x` (0..1) and time `t` (seconds) --
 * roughly -1..1, not yet shaped by an envelope. */
export function sampleWave(harmonics: Harmonic[], x: number, t: number): number {
  let sum = 0
  let totalAmp = 0
  for (const h of harmonics) {
    sum += Math.sin(x * h.freq * Math.PI * 2 + h.phase + t * h.speed) * h.amp
    totalAmp += h.amp
  }
  return totalAmp > 0 ? sum / totalAmp : 0
}

/** Tapers the wave toward zero at both edges (a half-sine window) so the shape reads as one
 * cohesive cluster -- like the reference's glowing blob -- rather than a flat oscillation
 * running wall-to-wall to the container's own edges. */
export function edgeEnvelope(x: number): number {
  return Math.sin(Math.PI * Math.min(1, Math.max(0, x)))
}
