import { useState } from 'react'
import { classNames } from '@/components/class-names'
import { IconChevronDown, IconChevronRight } from '@/components/icons'
import type { SceneNode } from '@/domain/scene'

function formatValue(node: Extract<SceneNode, { kind: 'value' }>): string {
  if (node.value === null) return 'null'
  if (node.hint === 'duration' && typeof node.value === 'number') {
    return `${(node.value / 1000).toFixed(2)}s`
  }
  return String(node.value)
}

function ValueRow({ node }: { node: Extract<SceneNode, { kind: 'value' }> }) {
  return (
    <div className="flex items-center gap-2 py-0.5 font-mono text-xs">
      <span className="text-ink-500">{node.label}</span>
      <span className="text-ink-300">·</span>
      {node.hint === 'color' && typeof node.value === 'string' && (
        <span
          aria-hidden
          className="h-3 w-3 rounded-full border border-ink-300/40"
          style={{ background: node.value }}
        />
      )}
      <span
        className={classNames(
          'text-ink-900',
          node.hint === 'code' && 'whitespace-pre-wrap',
        )}
      >
        {formatValue(node)}
      </span>
    </div>
  )
}

function Branch({ node, depth }: { node: SceneNode; depth: number }) {
  const [open, setOpen] = useState(depth < 2)

  if (node.kind === 'value') {
    return (
      <div style={{ marginLeft: depth * 14 }}>
        <ValueRow node={node} />
      </div>
    )
  }

  const count = node.kind === 'array' ? node.count : node.children.length

  return (
    <div style={{ marginLeft: depth === 0 ? 0 : 14 }}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 py-0.5 font-mono text-xs text-ink-700 hover:text-ink-900"
      >
        <span className="text-ink-300">
          {open ? <IconChevronDown /> : <IconChevronRight />}
        </span>
        <span>{node.label}</span>
        <span className="text-ink-300">
          {node.kind === 'array' ? `[${count}]` : `{${count}}`}
        </span>
      </button>
      {open && (
        <div className="border-l border-ink-300/20 pl-2">
          {node.children.map((child, i) => (
            <Branch key={i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

/** A generic, data-driven JSON tree -- deliberately the only way this app ever shows a scene.
 * See `adapters/scene-adapter.ts` for why per-block-type components are the wrong tool here. */
export function SceneTree({ tree }: { tree: SceneNode }) {
  return (
    <div className="rounded-md border border-ink-300/25 bg-paper-0 p-3">
      <Branch node={tree} depth={0} />
    </div>
  )
}
