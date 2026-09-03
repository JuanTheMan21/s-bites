import { getSegmentScene } from '@/api/endpoints'
import type { SceneNode, SceneValueHint } from '@/domain/scene'

const DURATION_KEY = /(_ms|duration)$/i
const REFERENCE_KEY = /(_key|_url)$/i
const HEX_COLOR = /^#[0-9a-f]{6}$/i
const CODE_KEYS = new Set(['code', 'source', 'snippet'])

function hintFor(key: string, value: unknown): SceneValueHint {
  if (typeof value === 'number' && DURATION_KEY.test(key)) return 'duration'
  if (typeof value === 'string') {
    if (HEX_COLOR.test(value)) return 'color'
    if (CODE_KEYS.has(key.toLowerCase()) || value.includes('\n')) return 'code'
    if (REFERENCE_KEY.test(key)) return 'key'
  }
  return 'plain'
}

/**
 * Normalises ANY JSON value into a `SceneNode` tree. This is the entire answer to
 * `Segment.scene` being maximally volatile (`domain/job.ts`'s classification): value hints are
 * inferred heuristically from key name and value shape, never from a hardcoded block schema, so
 * a new block type, a restructured layout, or a field nobody has invented yet all render
 * correctly on day one -- nothing in this function names a block type, a layout, or any T18
 * vocabulary at all.
 */
export function toSceneTree(value: unknown, label = 'scene'): SceneNode {
  if (Array.isArray(value)) {
    return {
      kind: 'array',
      label,
      count: value.length,
      children: value.map((item, i) => toSceneTree(item, String(i))),
    }
  }
  if (value !== null && typeof value === 'object') {
    const children = Object.entries(value as Record<string, unknown>).map(([key, v]) =>
      toSceneTree(v, key),
    )
    return { kind: 'object', label, children }
  }
  return {
    kind: 'value',
    label,
    value: value as string | number | boolean | null,
    hint: hintFor(label, value),
  }
}

/** Fetches one segment's raw scene payload and normalises it in one step -- the only place
 * `features/` reaches for a scene, so it never has to know `api/` exists. */
export async function fetchSceneTree(jobId: string, index: number): Promise<SceneNode> {
  const raw = await getSegmentScene(jobId, index)
  return toSceneTree(raw)
}
