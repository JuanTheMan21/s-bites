import { describe, expect, it } from 'vitest'
import { toSceneTree } from './scene-adapter'

describe('toSceneTree', () => {
  it('normalises a real, current scene shape', () => {
    const tree = toSceneTree({
      layout: 'SPLIT_HORIZONTAL',
      duration_ms: 4200,
      blocks: [{ type: 'BULLET_LIST', accent_color: '#e8542f' }],
    })
    expect(tree.kind).toBe('object')
    if (tree.kind !== 'object') throw new Error('unreachable')
    const byLabel = Object.fromEntries(tree.children.map((c) => [c.label, c]))
    expect(byLabel.duration_ms).toMatchObject({ kind: 'value', hint: 'duration', value: 4200 })
    expect(byLabel.blocks?.kind).toBe('array')
  })

  it('infers a color swatch hint from a hex value regardless of key name', () => {
    const tree = toSceneTree({ accent_color: '#123abc' })
    if (tree.kind !== 'object') throw new Error('unreachable')
    expect(tree.children[0]).toMatchObject({ hint: 'color', value: '#123abc' })
  })

  it('infers a code hint from multiline text without a hardcoded block schema', () => {
    const tree = toSceneTree({ snippet: 'line one\nline two' })
    if (tree.kind !== 'object') throw new Error('unreachable')
    expect(tree.children[0]).toMatchObject({ hint: 'code' })
  })

  it('is the decoupling test: renders an entirely invented, future scene shape without throwing', () => {
    // Nothing about this shape exists in the current backend -- a hypothetical T18 iteration
    // that adds a new block type, restructures the root, and nests arrays of arrays. If this
    // still produces a tree, T18 cannot break the frontend by changing Segment.scene's shape.
    const invented = {
      composition_v2: {
        camera_path: [
          { t: 0, pos: [0, 0, 0] },
          { t: 1, pos: [10, 0, 5] },
        ],
        overlays: {
          particle_system_id: 'confetti-burst',
          layers: [[{ mask_url: 'https://example.com/m.png' }], []],
        },
        new_block_type: 'HOLOGRAM_PROJECTION',
      },
    }
    expect(() => toSceneTree(invented)).not.toThrow()
    const tree = toSceneTree(invented)
    expect(tree.kind).toBe('object')
  })

  it('handles primitives and null at the root', () => {
    expect(toSceneTree(null)).toEqual({ kind: 'value', label: 'scene', value: null, hint: 'plain' })
    expect(toSceneTree(42, 'count')).toEqual({ kind: 'value', label: 'count', value: 42, hint: 'plain' })
  })
})
