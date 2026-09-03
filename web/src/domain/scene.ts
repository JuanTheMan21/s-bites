/** A generic, data-driven normalisation of `Segment.scene` -- deliberately the *only* type this
 * app ever gives that field. No block type, layout name, or T18 vocabulary appears anywhere in
 * this file; that is what lets `adapters/scene-adapter.ts` render any shape the backend produces,
 * including one that does not exist yet. See `domain/job.ts`'s classification for why. */

export type SceneValueHint = 'code' | 'color' | 'duration' | 'key' | 'plain'

export type SceneNode =
  | { kind: 'object'; label: string; children: SceneNode[] }
  | { kind: 'array'; label: string; children: SceneNode[]; count: number }
  | { kind: 'value'; label: string; value: string | number | boolean | null; hint: SceneValueHint }
