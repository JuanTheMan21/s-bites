import { STAGE_EVENT_NAME, openJobEventStream } from '@/api/events-source'
import { phaseForNode, type StageEvent } from '@/domain/stage'

export { STAGE_EVENT_NAME, openJobEventStream }

/** Parses one already-`JSON.parse`d SSE `data:` payload into a `StageEvent`. Never throws -- a
 * malformed or future-shaped payload becomes `{kind:'unknown'}` rather than crashing the stream,
 * since a dropped stage update is far cheaper than a broken progress page. */
export function toStageEvent(raw: unknown, at: number = Date.now()): StageEvent {
  if (typeof raw !== 'object' || raw === null) return { kind: 'unknown', raw, at }
  const obj = raw as Record<string, unknown>

  if (
    typeof obj.job_status === 'string' &&
    (obj.job_status === 'succeeded' || obj.job_status === 'failed')
  ) {
    // Missing `terminal` defaults to true (assume closed) rather than false (assume open) -- a
    // UI that thinks a finished stream is still live hangs forever; one that thinks a live
    // stream finished just misses a later update, which the next poll corrects.
    return { kind: 'status', status: obj.job_status, terminal: obj.terminal !== false, at }
  }
  if (typeof obj.node === 'string' && (obj.stage === 'start' || obj.stage === 'end')) {
    const { phase, label } = phaseForNode(obj.node)
    return {
      kind: 'transition',
      node: obj.node,
      phase,
      label,
      edge: obj.stage,
      segmentIndex: typeof obj.segment_index === 'number' ? obj.segment_index : undefined,
      segmentTitle: typeof obj.segment_title === 'string' ? obj.segment_title : undefined,
      at,
    }
  }
  return { kind: 'unknown', raw, at }
}
