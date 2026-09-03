import { describe, expect, it } from 'vitest'
import type { VideoJobDto } from '@/api/endpoints'
import { toJobView } from './job-adapter'

const baseDto: VideoJobDto = {
  job_id: 'j1',
  topic: 'Teach me about SQL injection',
  target_duration_ms: 420000,
  status: 'succeeded',
  created_at: '2026-09-03T00:00:00Z',
  segments: [
    {
      index: 0,
      title: 'Intro',
      summary: 'sets the stage',
      visual_intent: 'title_card',
      importance: 5,
      narration: 'Hello',
      duration_ms: 3000,
      tier: 2,
      scene: { layout: 'SPLIT_HORIZONTAL' },
      clip_key: 'j1/segments/0/clip.mp4',
    },
  ],
  video_key: 'j1/video.mp4',
  subtitles_key: 'j1/subs.srt',
  error: null,
}

describe('toJobView', () => {
  it('maps a real VideoJob DTO field for field', () => {
    const view = toJobView(baseDto)
    expect(view.jobId).toBe('j1')
    expect(view.status).toBe('succeeded')
    expect(view.videoKey).toBe('j1/video.mp4')
    expect(view.segments).toHaveLength(1)
    expect(view.segments[0]).toEqual({
      index: 0,
      title: 'Intro',
      summary: 'sets the stage',
      visualIntent: 'title_card',
      importance: 5,
      narration: 'Hello',
      durationMs: 3000,
      tier: 2,
      hasScene: true,
      clipKey: 'j1/segments/0/clip.mp4',
    })
  })

  it('does not throw when every optional field is missing', () => {
    const minimal = {
      job_id: 'j2',
      topic: 'x',
      target_duration_ms: 60000,
      status: 'queued',
    } as unknown as VideoJobDto
    const view = toJobView(minimal)
    expect(view.segments).toEqual([])
    expect(view.videoKey).toBeNull()
    expect(view.subtitlesKey).toBeNull()
    expect(view.error).toBeNull()
  })

  it('reports hasScene without ever inspecting the scene payload', () => {
    const withoutScene = {
      ...baseDto,
      segments: [{ ...baseDto.segments![0]!, scene: null }],
    }
    expect(toJobView(withoutScene).segments[0]!.hasScene).toBe(false)
  })
})
