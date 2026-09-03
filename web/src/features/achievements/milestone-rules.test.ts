import { describe, expect, it } from 'vitest'
import type { JobView } from '@/domain/job'
import { computeMilestones } from './milestone-rules'

function job(overrides: Partial<JobView>): JobView {
  return {
    jobId: 'j',
    topic: 'x',
    targetDurationMs: 420_000,
    status: 'succeeded',
    createdAt: '2026-01-01T00:00:00Z',
    segments: [],
    videoKey: null,
    subtitlesKey: null,
    error: null,
    ...overrides,
  }
}

describe('computeMilestones', () => {
  it('reports nothing for an empty job list', () => {
    expect(computeMilestones([])).toEqual([])
  })

  it('does not credit a queued or failed job as a completed video', () => {
    const milestones = computeMilestones([job({ status: 'queued' }), job({ status: 'failed' })])
    expect(milestones.find((m) => m.id === 'first-video')).toBeUndefined()
  })

  it('awards first-video on exactly one succeeded job', () => {
    const milestones = computeMilestones([job({})])
    expect(milestones.map((m) => m.id)).toContain('first-video')
    expect(milestones.map((m) => m.id)).not.toContain('five-videos')
  })

  it('awards five-videos once five have succeeded', () => {
    const milestones = computeMilestones(Array.from({ length: 5 }, () => job({})))
    expect(milestones.map((m) => m.id)).toContain('five-videos')
  })

  it('awards ten-minute only once a succeeded job actually targeted 10+ minutes', () => {
    const short = computeMilestones([job({ targetDurationMs: 420_000 })])
    expect(short.map((m) => m.id)).not.toContain('ten-minute')

    const long = computeMilestones([job({ targetDurationMs: 600_000 })])
    expect(long.map((m) => m.id)).toContain('ten-minute')
  })

  it('awards tier-two-heavy only when at least half the segments earned Tier 2', () => {
    const mostlyStatic = computeMilestones([
      job({
        segments: [
          { index: 0, title: 'a', summary: '', visualIntent: 'title_card', importance: 3, narration: null, durationMs: null, tier: 0, hasScene: true, clipKey: null },
          { index: 1, title: 'b', summary: '', visualIntent: 'title_card', importance: 3, narration: null, durationMs: null, tier: 0, hasScene: true, clipKey: null },
          { index: 2, title: 'c', summary: '', visualIntent: 'title_card', importance: 3, narration: null, durationMs: null, tier: 2, hasScene: true, clipKey: null },
        ],
      }),
    ])
    expect(mostlyStatic.map((m) => m.id)).not.toContain('tier-two-heavy')

    const mostlyAnimated = computeMilestones([
      job({
        segments: [
          { index: 0, title: 'a', summary: '', visualIntent: 'title_card', importance: 3, narration: null, durationMs: null, tier: 2, hasScene: true, clipKey: null },
          { index: 1, title: 'b', summary: '', visualIntent: 'title_card', importance: 3, narration: null, durationMs: null, tier: 2, hasScene: true, clipKey: null },
        ],
      }),
    ])
    expect(mostlyAnimated.map((m) => m.id)).toContain('tier-two-heavy')
  })
})
