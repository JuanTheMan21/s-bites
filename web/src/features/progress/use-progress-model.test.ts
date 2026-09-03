import { describe, expect, it } from 'vitest'
import type { SegmentView } from '@/domain/job'
import type { StageEvent } from '@/domain/stage'
import { deriveActiveSegmentIndex, deriveCurrentPhase, derivePhaseProgress } from './use-progress-model'

function segment(overrides: Partial<SegmentView>): SegmentView {
  return {
    index: 0,
    title: 'x',
    summary: '',
    visualIntent: 'title_card',
    importance: 3,
    narration: null,
    durationMs: null,
    tier: null,
    hasScene: false,
    clipKey: null,
    ...overrides,
  }
}

function transition(overrides: Partial<Extract<StageEvent, { kind: 'transition' }>>): StageEvent {
  return {
    kind: 'transition',
    node: 'synthesize_segment',
    phase: 'voice',
    label: 'Recording narration',
    edge: 'end',
    at: 0,
    ...overrides,
  }
}

describe('derivePhaseProgress', () => {
  it('is null with no segments yet', () => {
    expect(derivePhaseProgress('voice', [])).toBeNull()
  })

  it('is null for phases with no per-segment signal', () => {
    const segments = [segment({ index: 0 })]
    expect(derivePhaseProgress('outline', segments)).toBeNull()
    expect(derivePhaseProgress('budget', segments)).toBeNull()
    expect(derivePhaseProgress('visuals', segments)).toBeNull()
    expect(derivePhaseProgress('finalize', segments)).toBeNull()
  })

  it('fractions voice progress by measured duration', () => {
    const segments = [
      segment({ index: 0, durationMs: 1000 }),
      segment({ index: 1, durationMs: null }),
    ]
    expect(derivePhaseProgress('voice', segments)).toBe(0.5)
  })

  it('fractions scenes progress by hasScene', () => {
    const segments = [segment({ index: 0, hasScene: true }), segment({ index: 1, hasScene: false })]
    expect(derivePhaseProgress('scenes', segments)).toBe(0.5)
  })

  it('fractions render progress by clipKey', () => {
    const segments = [
      segment({ index: 0, clipKey: 'k' }),
      segment({ index: 1, clipKey: null }),
      segment({ index: 2, clipKey: null }),
    ]
    expect(derivePhaseProgress('render', segments)).toBeCloseTo(1 / 3)
  })
})

describe('deriveCurrentPhase', () => {
  it('defaults to outline before any transition arrives', () => {
    expect(deriveCurrentPhase([])).toBe('outline')
  })

  it('reflects the most recent transition event', () => {
    const events = [transition({ phase: 'voice', at: 1 }), transition({ phase: 'render', at: 2 })]
    expect(deriveCurrentPhase(events)).toBe('render')
  })

  it('ignores non-transition events when picking the current phase', () => {
    const events: StageEvent[] = [
      transition({ phase: 'render', at: 1 }),
      { kind: 'status', status: 'succeeded', terminal: true, at: 2 },
    ]
    expect(deriveCurrentPhase(events)).toBe('render')
  })
})

describe('deriveActiveSegmentIndex', () => {
  it('is null when no transition has carried a segment index yet', () => {
    expect(deriveActiveSegmentIndex([transition({ segmentIndex: undefined })])).toBeNull()
  })

  it('reflects the most recent segment-carrying transition', () => {
    const events = [
      transition({ segmentIndex: 0, at: 1 }),
      transition({ segmentIndex: 2, at: 2 }),
    ]
    expect(deriveActiveSegmentIndex(events)).toBe(2)
  })
})
