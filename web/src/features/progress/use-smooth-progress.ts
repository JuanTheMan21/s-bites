import { useEffect, useRef, useState } from 'react'

// How quickly the display value eases toward real progress when it jumps -- high enough that a
// real jump feels responsive, not sluggish.
const EASE_RATE = 4
// How quickly the display value creeps toward `ceilingPct` when `targetPct` hasn't moved -- low
// enough that the creep itself is never mistaken for a real jump, and it asymptotically
// approaches (never reaches) the ceiling.
const CREEP_RATE = 0.6

/** One tick of the ease/creep blend, pure and unit-testable: `display` eases toward whichever is
 * larger of `target` (real, verified progress) or a slow creep toward `ceiling` -- so idle
 * phases with no per-segment signal still visibly advance, but never past `ceiling` (the next
 * phase's own territory) and never in a way that could be mistaken for a real jump once one
 * actually arrives (`target` always wins the max once it moves).
 */
export function nextProgressValue(
  display: number,
  target: number,
  ceiling: number,
  dt: number,
): number {
  const safeCeiling = Math.max(ceiling, target)
  const creepAttractor = display + (safeCeiling - display) * CREEP_RATE * dt
  const attractor = Math.min(safeCeiling, Math.max(target, creepAttractor))
  return display + (attractor - display) * Math.min(1, EASE_RATE * dt)
}

/** Smoothly animates a displayed percentage toward `targetPct`, creeping toward `ceilingPct`
 * when `targetPct` hasn't moved -- the "loading must look evident even with nothing new to
 * report" half of T18L's brief. `prefers-reduced-motion` skips the animation loop entirely and
 * tracks `targetPct` directly.
 */
export function useSmoothProgress(targetPct: number, ceilingPct: number): number {
  const [displayPct, setDisplayPct] = useState(targetPct)
  const state = useRef({ display: targetPct, target: targetPct, ceiling: ceilingPct })
  // A lazy useState initializer, not a bare useRef(matchMedia(...)) -- React's own rules-of-hooks
  // purity check flags calling an impure API (matchMedia, like performance.now()) directly during
  // render, even one whose result is only kept from the first call. A lazy initializer is the
  // sanctioned way to compute an impure value exactly once.
  const [reduceMotion] = useState(
    () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches,
  )

  // Keep the ref in sync with the latest props in an effect, not during render -- mutating a ref
  // while rendering is a purity violation React's own rules-of-hooks lint catches. This effect
  // never calls setState synchronously (a separate lint rule against that) -- it only updates
  // the ref the rAF loop below reads from its own callback.
  useEffect(() => {
    state.current.target = targetPct
    state.current.ceiling = ceilingPct
  }, [targetPct, ceilingPct])

  useEffect(() => {
    if (reduceMotion) return

    let raf = requestAnimationFrame(loop)
    let last = performance.now()

    function loop(now: number) {
      const dt = Math.min(0.1, (now - last) / 1000)
      last = now
      const s = state.current
      s.display = nextProgressValue(s.display, s.target, s.ceiling, dt)
      setDisplayPct(s.display)
      raf = requestAnimationFrame(loop)
    }

    return () => cancelAnimationFrame(raf)
    // Only restarts if reduceMotion itself changes (it never does, post-mount) -- the loop
    // reads state.current every frame, so it never needs to restart when targetPct/ceilingPct
    // change.
  }, [reduceMotion])

  // Reduced motion: targetPct IS the display value -- a plain derived read, never a mirrored
  // state variable, so there's no synchronous setState-in-effect to avoid in the first place.
  return reduceMotion ? targetPct : displayPct
}
