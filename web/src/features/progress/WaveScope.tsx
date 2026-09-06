import { useEffect, useRef, useState } from 'react'
import { buildHarmonics, edgeEnvelope, sampleWave, type Harmonic } from './wave-shape'

interface Props {
  /** Deterministic per-job wave shape -- same seed always draws the same underlying harmonics
   * (D137's contract, preserved from the old bar track: same job, same shape). */
  seed: number
  /** 0..100, already smoothed by `useSmoothProgress` -- the boundary between the bright (real
   * progress made) and dim (not yet reached) halves of the wave IS the progress indicator here,
   * not a separate bar. */
  fillPct: number
}

const SAMPLE_COUNT = 160
const SCOPE_BG = '#0a0a0d'
const BRIGHT_COLOR = '#ff9a52'
const BRIGHT_GLOW = 'rgba(255, 138, 76, 0.55)'
const DIM_COLOR = 'rgba(255, 255, 255, 0.14)'

/** One layer's path: top edge is the wave's envelope-shaped magnitude above centre, bottom edge
 * mirrors it below -- a filled silhouette, not a stroked line, so it reads as one continuous
 * organic shape (the user's own ask: "not a couple of boxes patched up looking like a wave"). */
function pathForLayer(
  ctx: CanvasRenderingContext2D,
  harmonics: Harmonic[],
  t: number,
  width: number,
  height: number,
  ampScale: number,
) {
  const mid = height / 2
  const maxAmpPx = mid * 0.85 * ampScale
  ctx.beginPath()
  for (let i = 0; i <= SAMPLE_COUNT; i++) {
    const xNorm = i / SAMPLE_COUNT
    const magnitude = Math.abs(sampleWave(harmonics, xNorm, t)) * edgeEnvelope(xNorm) * maxAmpPx
    const x = xNorm * width
    const y = mid - magnitude
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  }
  for (let i = SAMPLE_COUNT; i >= 0; i--) {
    const xNorm = i / SAMPLE_COUNT
    const magnitude = Math.abs(sampleWave(harmonics, xNorm, t)) * edgeEnvelope(xNorm) * maxAmpPx
    const x = xNorm * width
    const y = mid + magnitude
    ctx.lineTo(x, y)
  }
  ctx.closePath()
}

function drawFrame(
  ctx: CanvasRenderingContext2D,
  harmonics: Harmonic[],
  t: number,
  width: number,
  height: number,
  fillPct: number,
) {
  ctx.clearRect(0, 0, width, height)
  ctx.fillStyle = SCOPE_BG
  ctx.fillRect(0, 0, width, height)

  const fillX = (Math.min(100, Math.max(0, fillPct)) / 100) * width
  // Three layered copies at different phase/amplitude offsets -- the bloom effect from the
  // reference image, built from the same harmonics rather than three unrelated shapes.
  const layers: { tOffset: number; ampScale: number; alpha: number }[] = [
    { tOffset: 0, ampScale: 1, alpha: 1 },
    { tOffset: 1.7, ampScale: 0.7, alpha: 0.5 },
    { tOffset: -2.3, ampScale: 0.45, alpha: 0.3 },
  ]

  for (const layer of layers) {
    // Bright half: left of the playhead, real progress made.
    ctx.save()
    ctx.beginPath()
    ctx.rect(0, 0, fillX, height)
    ctx.clip()
    ctx.globalAlpha = layer.alpha
    ctx.shadowColor = BRIGHT_GLOW
    ctx.shadowBlur = 14
    ctx.fillStyle = BRIGHT_COLOR
    pathForLayer(ctx, harmonics, t + layer.tOffset, width, height, layer.ampScale)
    ctx.fill()
    ctx.restore()

    // Dim half: right of the playhead, a quiet ghost of the same wave -- not yet reached.
    ctx.save()
    ctx.beginPath()
    ctx.rect(fillX, 0, width - fillX, height)
    ctx.clip()
    ctx.globalAlpha = layer.alpha
    ctx.shadowBlur = 0
    ctx.fillStyle = DIM_COLOR
    pathForLayer(ctx, harmonics, t + layer.tOffset, width, height, layer.ampScale)
    ctx.fill()
    ctx.restore()
  }
}

/** The waveform loader itself: a dark inset "scope" panel with a continuously flowing wave,
 * bright where real progress has been made and dim beyond it -- the boundary between the two IS
 * the progress indicator, legible at a glance rather than needing a separate thin bar.
 * `ClipTrack.tsx` overlays the existing playhead marker on top of this at the same `fillPct`. */
// A frame that throws (any browser/GPU/extension quirk that makes 2D canvas drawing misbehave,
// not just theoretical) used to permanently kill the rAF loop with zero recovery and zero visible
// error -- the loop's own `requestAnimationFrame(frame)` call sat AFTER the draw call, so an
// exception skipped it and nothing ever scheduled another frame again. Found live: a real user's
// browser showed nothing but this component's own dark background (plus the separate, unaffected
// DOM playhead marker riding on top) -- exactly what a silently-dead canvas looks like, and it
// could not be reproduced in this project's own test browser, so the actual trigger is unconfirmed.
// Fixed on two levels: a failed draw no longer stops the loop (caught, logged, retried next
// frame), and if drawing keeps failing or a 2D context can never be obtained at all, this falls
// back to a plain CSS progress bar rather than a dead black box forever.
const MAX_CONSECUTIVE_DRAW_FAILURES = 5

export function WaveScope({ seed, fillPct }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  // buildHarmonics is pure and deterministic on seed -- calling it during render (the initial
  // useRef value) is not a purity violation the way performance.now()/matchMedia would be.
  const harmonicsRef = useRef(buildHarmonics(seed))
  const fillRef = useRef(fillPct)
  const [canvasFailed, setCanvasFailed] = useState(false)

  useEffect(() => {
    harmonicsRef.current = buildHarmonics(seed)
  }, [seed])

  // Keep the ref in sync with the latest fillPct in an effect, not during render -- mutating a
  // ref while rendering is a purity violation React's own rules-of-hooks lint now catches.
  useEffect(() => {
    fillRef.current = fillPct
  }, [fillPct])

  useEffect(() => {
    if (canvasFailed) return
    const canvas = canvasRef.current
    let ctx: CanvasRenderingContext2D | null = null
    try {
      ctx = canvas?.getContext('2d') ?? null
    } catch (err) {
      console.error('WaveScope: canvas.getContext("2d") threw', err)
    }
    if (!canvas || !ctx) {
      console.error('WaveScope: no 2D canvas context available, falling back to a plain bar')
      // Deferred, not called synchronously in the effect body -- react-hooks/set-state-in-effect
      // wants setState reserved for callbacks, even a one-off failure path like this one.
      queueMicrotask(() => setCanvasFailed(true))
      return
    }
    const readyCtx = ctx

    const reduceMotion =
      typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
    // Captured once, here inside the effect (never during render) -- only relative elapsed time
    // matters for the wave's own phase, so an arbitrary zero point is fine.
    const start = performance.now()

    function resize() {
      if (!canvas) return
      const dpr = window.devicePixelRatio || 1
      const rect = canvas.getBoundingClientRect()
      canvas.width = Math.max(1, Math.round(rect.width * dpr))
      canvas.height = Math.max(1, Math.round(rect.height * dpr))
      readyCtx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    resize()
    const observer = new ResizeObserver(resize)
    observer.observe(canvas)

    let raf = 0
    let consecutiveFailures = 0
    function frame(now: number) {
      try {
        const rect = canvas!.getBoundingClientRect()
        const t = (now - start) / 1000
        drawFrame(readyCtx, harmonicsRef.current, t, rect.width, rect.height, fillRef.current)
        consecutiveFailures = 0
      } catch (err) {
        consecutiveFailures += 1
        console.error('WaveScope: draw frame failed', err)
        if (consecutiveFailures >= MAX_CONSECUTIVE_DRAW_FAILURES) {
          setCanvasFailed(true)
          return
        }
      }
      raf = requestAnimationFrame(frame)
    }

    if (reduceMotion) {
      try {
        const rect = canvas.getBoundingClientRect()
        drawFrame(readyCtx, harmonicsRef.current, 0, rect.width, rect.height, fillRef.current)
      } catch (err) {
        console.error('WaveScope: static draw failed', err)
        queueMicrotask(() => setCanvasFailed(true))
      }
    } else {
      raf = requestAnimationFrame(frame)
    }

    return () => {
      observer.disconnect()
      if (raf) cancelAnimationFrame(raf)
    }
  }, [canvasFailed])

  if (canvasFailed) {
    return (
      <div className="relative h-[88px] w-full overflow-hidden rounded-md" style={{ background: SCOPE_BG }}>
        <div
          aria-hidden
          className="absolute inset-y-0 left-0"
          style={{
            width: `${Math.min(100, Math.max(0, fillPct))}%`,
            background: BRIGHT_COLOR,
            boxShadow: `0 0 14px 2px ${BRIGHT_GLOW}`,
            transition: 'width 0.2s linear',
          }}
        />
      </div>
    )
  }

  return (
    <div className="relative h-[88px] w-full overflow-hidden rounded-md" style={{ background: SCOPE_BG }}>
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" aria-hidden />
    </div>
  )
}
