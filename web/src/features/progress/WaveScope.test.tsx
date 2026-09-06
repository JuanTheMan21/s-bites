import { cleanup, render, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { WaveScope } from './WaveScope'

afterEach(cleanup)

// jsdom has no real 2D canvas backend (the optional `canvas` npm package isn't installed), so
// `HTMLCanvasElement.prototype.getContext('2d')` returns null here by construction -- exactly
// the failure mode a real user's browser hit live (D172): no context, no drawing, and before
// this fix, a dead black box forever with nothing else rendered. This suite exercises the
// fallback path for free, with no mocking required, rather than testing something jsdom cannot
// actually verify (real wave pixels). The fallback itself lands one microtask after mount
// (`queueMicrotask`, deliberately deferred so setState is never called synchronously inside the
// effect body), so every assertion here waits for it rather than checking immediately.
describe('WaveScope', () => {
  it('falls back to a plain progress bar when no 2D context is available, instead of rendering nothing', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const { container } = render(<WaveScope seed={6} fillPct={42} />)

    // The canvas element itself is gone once the fallback kicks in -- not left mounted and
    // silently blank.
    await waitFor(() => expect(container.querySelector('canvas')).toBeNull())
    const bar = container.querySelector('[aria-hidden]') as HTMLElement | null
    expect(bar).not.toBeNull()
    // scaleX, not width -- a layout property would reflow on every tick; transform is
    // compositor-only (found by the project's own design hook, fixed alongside this suite).
    expect(bar!.style.transform).toBe('scaleX(0.42)')

    errorSpy.mockRestore()
  })

  it('clamps the fallback bar scale into 0..1 regardless of an out-of-range fillPct', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})

    const { container, rerender } = render(<WaveScope seed={1} fillPct={150} />)
    await waitFor(() => expect(container.querySelector('canvas')).toBeNull())
    let bar = container.querySelector('[aria-hidden]') as HTMLElement
    expect(bar.style.transform).toBe('scaleX(1)')

    rerender(<WaveScope seed={1} fillPct={-10} />)
    bar = container.querySelector('[aria-hidden]') as HTMLElement
    expect(bar.style.transform).toBe('scaleX(0)')

    vi.restoreAllMocks()
  })

  it('logs to console.error rather than failing silently when the context is unavailable', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(<WaveScope seed={3} fillPct={10} />)

    await waitFor(() => expect(errorSpy).toHaveBeenCalled())
    errorSpy.mockRestore()
  })
})
