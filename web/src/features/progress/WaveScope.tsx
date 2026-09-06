import { useEffect, useRef } from 'react'
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
export function WaveScope({ seed, fillPct }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  // buildHarmonics is pure and deterministic on seed -- calling it during render (the initial
  // useRef value) is not a purity violation the way performance.now()/matchMedia would be.
  const harmonicsRef = useRef(buildHarmonics(seed))
  const fillRef = useRef(fillPct)

  useEffect(() => {
    harmonicsRef.current = buildHarmonics(seed)
  }, [seed])

  // Keep the ref in sync with the latest fillPct in an effect, not during render -- mutating a
  // ref while rendering is a purity violation React's own rules-of-hooks lint now catches.
  useEffect(() => {
    fillRef.current = fillPct
  }, [fillPct])

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return

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
      ctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    resize()
    const observer = new ResizeObserver(resize)
    observer.observe(canvas)

    let raf = 0
    function frame(now: number) {
      const rect = canvas!.getBoundingClientRect()
      const t = (now - start) / 1000
      drawFrame(ctx!, harmonicsRef.current, t, rect.width, rect.height, fillRef.current)
      raf = requestAnimationFrame(frame)
    }

    if (reduceMotion) {
      const rect = canvas.getBoundingClientRect()
      drawFrame(ctx, harmonicsRef.current, 0, rect.width, rect.height, fillRef.current)
    } else {
      raf = requestAnimationFrame(frame)
    }

    return () => {
      observer.disconnect()
      if (raf) cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <div className="relative h-[88px] w-full overflow-hidden rounded-md" style={{ background: SCOPE_BG }}>
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" aria-hidden />
    </div>
  )
}
